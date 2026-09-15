#!/usr/bin/env python3
"""
density_check.py — Công cụ hỗ trợ gate R-1 (đếm tay density) cho Ralion F6/UC-1.

VAI TRÒ CỦA SCRIPT NÀY — đọc trước khi chạy:
  Script KHÔNG quyết định GO/NO-GO cho repo. Nó chỉ làm hai việc:
    1. Đếm population thật (PR merged trong window, đã trừ bot) — con số khách quan.
    2. Lấy MỘT SAMPLE ngẫu nhiên các PR, fetch toàn bộ review comment, áp heuristic lọc
       noise thô (Open Question #4 của spec), rồi xuất ra CSV để CON NGƯỜI đọc và đếm tay
       thật — đúng tinh thần "Density đếm tay (gate R-1)" trong PRD (mục 13).
  Lý do KHÔNG tự động hoá toàn bộ: bản thân spec đã chốt "không dùng AI để phân loại"
  ở bước gắn doc_type (Open Question #1), và gate R-1 là gate đếm tay theo thiết kế —
  tự động hoá 100% bước này sẽ phá vỡ đúng nguyên tắc mà PRD đang cố giữ (tránh việc
  AI tự đánh giá chất lượng dữ liệu đầu vào cho chính AI dùng).

PHÁT HIỆN THỰC NGHIỆM cần biết trước khi đọc kết quả:
  Kiểm tra nhanh trên vuejs/core (Jan 2024, n=30 PR mẫu) cho thấy ~37% PR merged là
  bot-authored (renovate[bot], dependabot[bot]) — dependency bump vô nghĩa với rule
  mining. Open Question #4 gốc chỉ lọc comment noise, KHÔNG lọc PR noise theo tác giả.
  Script này bổ sung bước lọc bot ở cấp PR (is_bot) trước khi tính population thật,
  vì nếu không, "PR count" sẽ đánh lừa gate R-1 theo hướng lạc quan giả.

CÁCH DÙNG:
  export GITHUB_TOKEN=ghp_xxx   # bắt buộc — rate limit unauth quá thấp (60/h core, 10/phút search)
  python3 density_check.py --repo thanos-io/thanos --since 2024-01-01 --until 2025-06-30 \
      --sample-size 120 --out thanos

  Nếu cần thu hẹp vào 1 vùng code cụ thể (giảm nhiễu domain, review tập trung hơn):
  python3 density_check.py --repo thanos-io/thanos --since 2024-01-01 --until 2025-06-30 \
      --path-filter pkg/store/ --sample-size 120 --out thanos_store

NGUỒN DỮ LIỆU (3 loại, gộp chung 1 corpus, phân biệt bằng cột 'type'):
  - review_comment(diff)     — comment gắn trực tiếp vào 1 dòng diff.
  - issue_comment(conversation) — comment cấp hội thoại chung của PR.
  - review(summary)          — nội dung tóm tắt khi reviewer submit 1 review
                                (APPROVED/CHANGES_REQUESTED/COMMENTED). Đây thường
                                là nơi CONVENTION-type feedback ("we usually...",
                                "please follow...") xuất hiện nhiều nhất — bỏ sót
                                nguồn này sẽ làm density đo được thấp hơn thực tế.
                                Cột 'review_state' chỉ có giá trị cho type này.

OUTPUT:
  <out>_summary.json        — số liệu tổng hợp population + sample, có breakdown
                               theo từng loại nguồn (comments_by_type)
  <out>_comments_sample.csv — TỪNG comment/review trong sample, kèm:
                               - survived_filter (qua heuristic filter thô)
                               - sample_stratum (HAS_SURVIVOR / NO_SURVIVOR theo PR —
                                 dùng để annotator lọc và đọc theo đúng thứ tự ưu
                                 tiên trong annotation_guide.md mục 1)
                               (đây là file bạn/team ngồi đọc tay để đối chiếu
                               ground truth, không phải file để tin tuyệt đối)
"""

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

# Script này tự nhận chạy độc lập, không cần pip install (xem HTTP layer bên dưới) —
# nhưng vẫn tái dùng 2 module production stdlib-only (GithubClient, pr_corpus_filters)
# thay vì giữ 1 bản is_bot/is_noise/fetch_pr_reviews thứ hai trôi dạt khỏi bản gốc.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.modules.knowledge.ingestion.github_client import GithubClient  # noqa: E402
from src.modules.knowledge.ingestion.pr_corpus_filters import is_bot, is_noise  # noqa: E402

API = "https://api.github.com"
CACHE_DIR = ".density_check_cache"

# ---------------------------------------------------------------------------
# HTTP layer: cache-on-disk + rate-limit-aware retry. Stdlib only, không cần
# pip install gì — script này chạy một lần, không đáng để kéo thêm dependency.
# ---------------------------------------------------------------------------

def _cache_path(url):
    os.makedirs(CACHE_DIR, exist_ok=True)
    h = hashlib.sha256(url.encode()).hexdigest()[:24]
    return os.path.join(CACHE_DIR, h + ".json")


def gh_get(url, token, use_cache=True):
    """GET một URL GitHub API, có cache đĩa + retry khi rate-limited."""
    cpath = _cache_path(url)
    if use_cache and os.path.exists(cpath):
        with open(cpath, encoding="utf-8") as f:
            return json.load(f)

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(6):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
                remaining = resp.headers.get("X-RateLimit-Remaining")
                if remaining is not None and int(remaining) < 3:
                    reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                    sleep_s = max(reset - time.time(), 1) + 2
                    print(f"  [rate-limit] gần cạn ({remaining} left), ngủ {sleep_s:.0f}s...", file=sys.stderr)
                    time.sleep(sleep_s)
                if use_cache:
                    with open(cpath, "w", encoding="utf-8") as f:
                        json.dump(data, f)
                return data
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                retry_after = e.headers.get("Retry-After")
                sleep_s = int(retry_after) if retry_after else (2 ** attempt) * 5
                print(f"  [http {e.code}] backoff {sleep_s}s (attempt {attempt+1}/6)...", file=sys.stderr)
                time.sleep(sleep_s)
                continue
            elif e.code == 422:
                print(f"  [http 422] query có thể sai cú pháp: {url}", file=sys.stderr)
                raise
            else:
                raise
    raise RuntimeError(f"Fetch thất bại sau nhiều lần retry: {url}")


# ---------------------------------------------------------------------------
# Bước 1-3 (liệt kê PR, path-filter, fetch comment/review, is_bot/is_noise):
# giờ dùng chung GithubClient + pr_corpus_filters (xem import ở đầu file) thay
# vì giữ bản HTTP-fetch/filter thứ hai ở đây — production F6 sẽ tái dùng đúng
# 2 module đó, không dựng lại từ script này.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/name, vd: vuejs/core")
    ap.add_argument("--since", required=True, help="YYYY-MM-DD")
    ap.add_argument("--until", required=True, help="YYYY-MM-DD")
    ap.add_argument("--path-filter", default=None, help="vd: packages/reactivity/ (optional)")
    ap.add_argument("--sample-size", type=int, default=120)
    ap.add_argument("--max-checked-for-path-filter", type=int, default=500,
                     help="Trần số PR kiểm tra files khi có --path-filter, tránh đốt hết rate limit")
    ap.add_argument("--out", required=True, help="tiền tố tên file output")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--extra-bot-logins", default="",
                     help="danh sách login bot bổ sung, phân cách bởi dấu phẩy "
                          "(vd: 'triage-bot,ci-runner') — dùng khi tally cho thấy "
                          "account lạ nghi là bot nhưng chưa nằm trong KNOWN_NON_SUFFIX_BOTS")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("CẢNH BÁO: chưa set GITHUB_TOKEN — rate limit unauth (60/h core, 10/phút search) "
              "sẽ khiến script này gần như không chạy hết nổi 1 tháng dữ liệu. "
              "export GITHUB_TOKEN=ghp_... rồi chạy lại.", file=sys.stderr)

    random.seed(args.seed)

    # transport=gh_get: GithubClient thực hiện fetch/shape (list PR, comment, review),
    # nhưng dùng đúng gh_get cache-trên-đĩa + rate-limit backoff của script này làm
    # transport — giữ nguyên hành vi cache/rerun hiện tại thay vì chuyển sang retry
    # policy khác của GithubClient (dành cho production, không cache đĩa).
    client = GithubClient(token, transport=lambda url: gh_get(url, token))

    print(f"=== Bước 1/3: liệt kê PR merged, {args.repo}, {args.since}..{args.until} ===")
    all_prs = [
        {"number": p.number, "title": p.title, "author": p.author, "is_bot": is_bot(p.author), "html_url": p.html_url}
        for p in client.list_merged_prs(args.repo, date.fromisoformat(args.since), date.fromisoformat(args.until))
    ]
    human_prs = [p for p in all_prs if not p["is_bot"]]
    bot_prs = [p for p in all_prs if p["is_bot"]]
    print(f"  Tổng PR merged: {len(all_prs)}  |  bot: {len(bot_prs)} "
          f"({100*len(bot_prs)/max(len(all_prs),1):.0f}%)  |  human: {len(human_prs)}")

    print(f"\n=== Bước 2/3: chọn sample (n={args.sample_size}) ===")
    pool = human_prs[:]
    random.shuffle(pool)
    sample = []
    checked = 0

    if args.path_filter:
        print(f"  Có path-filter='{args.path_filter}' — cần check pulls/*/files từng PR "
              f"(tốn thêm {min(len(pool), args.max_checked_for_path_filter)} API call)")
        for pr in pool:
            if len(sample) >= args.sample_size or checked >= args.max_checked_for_path_filter:
                break
            checked += 1
            if client.pr_touches_path(args.repo, pr["number"], args.path_filter):
                sample.append(pr)
            if checked % 50 == 0:
                print(f"  ...đã check {checked} PR, tìm được {len(sample)} match path-filter")
        print(f"  Kết quả: {len(sample)}/{checked} PR chạm '{args.path_filter}' "
              f"(tỷ lệ ~{100*len(sample)/max(checked,1):.0f}% trong số đã check — "
              f"KHÔNG suy ra tỷ lệ này đúng cho toàn population, chỉ đúng cho phần đã check)")
    else:
        sample = pool[:args.sample_size]

    if not sample:
        print("KHÔNG có PR nào trong sample — dừng. Kiểm tra lại path-filter hoặc window ngày.")
        sys.exit(1)

    extra_bots = {b.strip().lower() for b in args.extra_bot_logins.split(",") if b.strip()}

    print(f"\n=== Bước 3/3: fetch + lọc comment/review cho {len(sample)} PR trong sample ===")
    all_comments = []
    for i, pr in enumerate(sample, 1):
        # 3 nguồn gộp chung: review_comment(diff), issue_comment(conversation),
        # review(summary) — nguồn thứ 3 trước đây bị bỏ sót, xem GithubClient.fetch_pr_reviews().
        items = [
            {
                "pr_number": c.pr_number, "type": c.kind, "author": c.author,
                "is_bot_comment": is_bot(c.author, extra_bots), "body": c.body,
                "url": c.html_url, "created_at": c.created_at,
                "review_state": "", "in_reply_to_id": c.in_reply_to_id or "",
            }
            for c in client.fetch_pr_comments(args.repo, pr["number"])
        ] + [
            {
                "pr_number": r.pr_number, "type": "review(summary)", "author": r.author,
                "is_bot_comment": is_bot(r.author, extra_bots), "body": r.body,
                "url": r.html_url, "created_at": r.submitted_at,
                "review_state": r.state, "in_reply_to_id": "",
            }
            for r in client.fetch_pr_reviews(args.repo, pr["number"])
        ]
        for c in items:
            c["pr_author"] = pr["author"]
            # Comment/review của bot bị loại HOÀN TOÀN khỏi candidate pool ngay từ đây —
            # không đi qua is_noise (nhiều bot message dài, đủ 10 từ, sẽ "sống sót"
            # sai nếu không chặn trước — xác nhận thực nghiệm: github-actions[bot],
            # bors, rustbot, vue-bot đều post message dài).
            if c["is_bot_comment"]:
                c["survived_filter"] = False
            else:
                c["survived_filter"] = not is_noise(c["body"])
        all_comments.extend(items)
        if i % 20 == 0:
            print(f"  ...{i}/{len(sample)} PR đã fetch, {len(all_comments)} dòng gom được")

    bot_comments = [c for c in all_comments if c["is_bot_comment"]]
    human_comments = [c for c in all_comments if not c["is_bot_comment"]]
    survived = [c for c in human_comments if c["survived_filter"]]
    # loại tự-comment (PR author reply comment của chính mình) khỏi "reviewer" thật
    distinct_reviewers_survived_excl_author = {
        c["author"] for c in survived if c["author"] != c["pr_author"]
    }
    prs_with_survivor = {c["pr_number"] for c in survived}

    # sample_stratum: bắt buộc cho annotation_guide.md mục 1/5/6 — annotator lọc
    # và đọc theo nhóm này, KHÔNG tính tay. HAS_SURVIVOR nếu PR có ≥1 dòng (thuộc
    # bất kỳ nguồn nào trong 3 nguồn) sống sót qua filter thô.
    for c in all_comments:
        c["sample_stratum"] = "HAS_SURVIVOR" if c["pr_number"] in prs_with_survivor else "NO_SURVIVOR"

    comments_by_type = Counter(c["type"] for c in all_comments)
    survived_by_type = Counter(c["type"] for c in survived)

    # Cảnh báo mềm: account nào có "bot" trong tên nhưng chưa nằm trong danh sách
    # đã biết (KNOWN_NON_SUFFIX_BOTS + --extra-bot-logins) và xuất hiện đủ nhiều
    # để đáng nghi — in ra để người review tự quyết định, KHÔNG tự động loại
    # (giữ đúng nguyên tắc "không dùng AI/heuristic mù để tự phân loại").
    all_authors_count = Counter(c["author"] for c in all_comments)
    suspicious = [
        (a, n) for a, n in all_authors_count.items()
        if "bot" in a.lower() and not is_bot(a, extra_bots) and n >= 3
    ]
    if suspicious:
        print("\n  [CẢNH BÁO] Account chứa 'bot' trong tên nhưng chưa được lọc, "
              "xuất hiện ≥3 lần — kiểm tra tay xem có phải bot không:")
        for a, n in sorted(suspicious, key=lambda x: -x[1]):
            print(f"    {a}: {n} lần — nếu đúng là bot, thêm vào --extra-bot-logins")

    summary = {
        "repo": args.repo, "window": [args.since, args.until],
        "path_filter": args.path_filter,
        "population_total_merged_prs": len(all_prs),
        "population_bot_prs": len(bot_prs),
        "population_bot_ratio": round(len(bot_prs) / max(len(all_prs), 1), 3),
        "population_human_prs": len(human_prs),
        "sample_size_prs": len(sample),
        "sample_checked_for_path_filter": checked if args.path_filter else None,
        "comments_total_fetched": len(all_comments),
        "bot_comments_excluded": len(bot_comments),
        "bot_comment_ratio": round(len(bot_comments) / max(len(all_comments), 1), 3),
        "human_comments_total": len(human_comments),
        "human_comments_survived_filter": len(survived),
        "survival_rate_among_human": round(len(survived) / max(len(human_comments), 1), 3),
        "prs_with_at_least_1_survivor": len(prs_with_survivor),
        "distinct_reviewer_logins_survived": len(distinct_reviewers_survived_excl_author),
        "candidate_density_per_pr": round(len(survived) / max(len(sample), 1), 2),
        "comments_by_type": dict(comments_by_type),
        "survived_by_type": dict(survived_by_type),
    }

    with open(f"{args.out}_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    with open(f"{args.out}_comments_sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "pr_number", "type", "author", "is_bot_comment", "pr_author",
            "survived_filter", "sample_stratum", "review_state", "in_reply_to_id",
            "word_count", "body", "url", "created_at",
        ])
        w.writeheader()
        for c in all_comments:
            body_norm = re.sub(r"\s+", " ", c["body"]).strip()
            w.writerow({
                "pr_number": c["pr_number"], "type": c["type"], "author": c["author"],
                "is_bot_comment": c["is_bot_comment"], "pr_author": c["pr_author"],
                "survived_filter": c["survived_filter"],
                "sample_stratum": c["sample_stratum"],
                "review_state": c.get("review_state", ""),
                "in_reply_to_id": c.get("in_reply_to_id", ""),
                "word_count": len(body_norm.split()), "body": body_norm,
                "url": c["url"], "created_at": c["created_at"],
            })

    print("\n" + "=" * 70)
    print(f"KẾT QUẢ — {args.repo}")
    print("=" * 70)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("=" * 70)
    print(f"-> {args.out}_summary.json  (số liệu tổng hợp)")
    print(f"-> {args.out}_comments_sample.csv  (MỞ FILE NÀY VÀ ĐỌC TAY — đây mới là gate R-1 thật)")
    print("\nLưu ý bắt buộc đọc:")
    print("  - 'candidate_density_per_pr' là ước lượng THÔ trên sample, không phải ground truth.")
    print("  - Bước tiếp theo BẮT BUỘC: người thật mở file CSV, đọc cột 'body' của các dòng")
    print("    survived_filter=True, tự đánh giá bao nhiêu % thực sự là correction/convention")
    print("    (không phải câu hỏi thuần tuý, không phải thảo luận không có kết luận).")
    print("    Đây chính là 'Density đếm tay (gate R-1)' trong PRD mục 13 — script chỉ")
    print("    thu hẹp candidate pool để việc đếm tay khả thi trong vài giờ thay vì vài tuần.")


if __name__ == "__main__":
    main()