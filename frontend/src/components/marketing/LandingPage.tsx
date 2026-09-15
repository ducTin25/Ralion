"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  LayoutList,
  MessageSquare,
  FileText,
  CheckSquare,
  ArrowRight,
  Play,
  Check,
  Map,
  BarChart3,
  Sparkles,
  Globe,
  ExternalLink,
  Code2,
  Users,
  ShieldCheck,
  Mail,
  X,
  Send,
  Search,
  Workflow,
  Database,
  Cloud,
  Container,
} from "lucide-react";

import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { Link } from "@/i18n/navigation";
import styles from "./LandingPage.module.css";

const RALION_DEMO_VIDEO_URL =
  "https://drive.google.com/file/d/1HBQRfdPjs04os6Jf5cpsWOEExv6TkDZe/preview";

/* ─── Product mockup components ─────────────────────────────── */
function AppMockup({ locale }: { locale: string }) {
  const isVi = locale === "vi";
  return (
    <div className={styles.appMockup}>
      {/* Window chrome */}
      <div className={styles.appBar}>
        <div className={styles.trafficDots}>
          <span className={styles.trafficDot} style={{ background: "#FF5F57" }} />
          <span className={styles.trafficDot} style={{ background: "#FEBC2E" }} />
          <span className={styles.trafficDot} style={{ background: "#28C840" }} />
        </div>
        <div className={styles.appBarCenter}>
          <Search size={12} className={styles.appBarSearchIcon} />
          <span className={styles.appBarTitle}>Ralion Assistant · FURNISTORE</span>
        </div>
        <span className={styles.appBadge}>
          <span className={styles.liveDot} />
          {isVi ? "Tri thức sẵn sàng" : "Knowledge ready"}
        </span>
      </div>

      {/* App body */}
      <div className={styles.appBody}>
        {/* Sidebar */}
        <aside className={styles.appSidebar}>
          <span className={styles.sideLogoR}>R</span>
          <span className={`${styles.sideItem} ${styles.sideItemActive}`} />
          <span className={styles.sideItem} />
          <span className={styles.sideItem} />
          <span className={styles.sideItem} />
        </aside>

        {/* Conversation */}
        <div className={styles.appConvo}>
          <p className={styles.convoLabel}>
            {isVi ? "HỎI TRONG NGỮ CẢNH DỰ ÁN & CHÍNH SÁCH" : "QUERY IN CONTEXT & POLICIES"}
          </p>

          <div className={styles.convoQ}>
            {isVi
              ? "Quy trình review pull request & chính sách bảo mật repo là gì?"
              : "What is the PR review process and repository security policy?"}
          </div>

          <div className={styles.convoA}>
            <span className={styles.convoAvatar}>R</span>
            <div className={styles.convoAnswer}>
              <strong>Ralion AI</strong>
              <p>
                {isVi
                  ? "Mọi pull request cần ít nhất một approval từ Tech Lead, CI pass 100% và tuân thủ chính sách IT-03 về bảo mật secret."
                  : "All PRs require at least one Tech Lead approval, 100% green CI, and compliance with IT-03 security policy."}
              </p>
              <div className={styles.convoCites}>
                <span>CONTRIBUTING.md</span>
                <span>sec_01_phan_quyen.md</span>
                <span>quy_uoc_gitflow</span>
              </div>
            </div>
          </div>

          <div className={styles.convoSources}>
            <span className={styles.sourceAvatars}>
              <i /><i /><i />
            </span>
            {isVi ? "3 nguồn đã được đối chiếu và xác thực" : "3 verified sources matched"}
          </div>

          {/* Interactive prompt mockup at bottom */}
          <div className={styles.mockInputBar}>
            <span className={styles.mockInputPlaceholder}>
              {isVi
                ? "Hỏi Ralion về repo, setup môi trường, chính sách IT/HR..."
                : "Ask Ralion about repo, local setup, IT/HR policies..."}
            </span>
            <button className={styles.mockSendBtn} type="button" aria-label="Send">
              <Send size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PlanMockup({ locale }: { locale: string }) {
  const isVi = locale === "vi";
  const tasks = isVi
    ? [
        { done: true, cat: "TÀI LIỆU", label: "Đọc tài liệu Overview & Architecture dự án" },
        { done: true, cat: "CHÍNH SÁCH", label: "Xác nhận chính sách IT & Bảo mật thông tin" },
        { done: false, cat: "MÔI TRƯỜNG", label: "Cài đặt môi trường dev local & Docker", active: true },
        { done: false, cat: "CODEBASE", label: "Đọc Codebase Style Guide & quy ước Gitflow" },
      ]
    : [
        { done: true, cat: "OVERVIEW", label: "Read Project Overview & Architecture docs" },
        { done: true, cat: "POLICY", label: "Acknowledge IT & InfoSec Policies" },
        { done: false, cat: "SETUP", label: "Setup local development environment & Docker", active: true },
        { done: false, cat: "CODEBASE", label: "Read Codebase Style Guide & Gitflow" },
      ];

  return (
    <div className={styles.planMockup}>
      <div className={styles.planHead}>
        <span className={styles.planBadge}>DRAFT</span>
        <span className={styles.planName}>
          {isVi ? "Onboarding Plan · Nguyễn A" : "Onboarding Plan · Alex N."}
        </span>
        <span className={styles.planVer}>{isVi ? "Phiên bản 1" : "Version 1"}</span>
      </div>
      <div className={styles.planList}>
        {tasks.map((tk, i) => (
          <div
            className={`${styles.planTask} ${tk.active ? styles.planActive : ""}`}
            key={i}
          >
            <span className={`${styles.planCb} ${tk.done ? styles.planDone : ""}`}>
              {tk.done && <Check size={11} strokeWidth={3} />}
            </span>
            <div>
              <small>{tk.cat}</small>
              <p>{tk.label}</p>
            </div>
          </div>
        ))}
      </div>
      <div className={styles.planFoot}>
        <span>{isVi ? "7/7 task · 14 trích dẫn nguồn" : "7/7 tasks · 14 citations"}</span>
        <button className={styles.planBtn}>
          {isVi ? "Duyệt & Phát hành" : "Approve & Publish"}
        </button>
      </div>
    </div>
  );
}

function DashMockup({ locale }: { locale: string }) {
  const isVi = locale === "vi";
  const kpis = isVi
    ? [
        { val: "8", label: "Đang onboarding", color: "#252525" },
        { val: "67%", label: "Tiến độ TB", color: "#1090CB" },
        { val: "2", label: "Blocker mở", color: "#d64f2d" },
      ]
    : [
        { val: "8", label: "Active Onboarding", color: "#252525" },
        { val: "67%", label: "Avg Progress", color: "#1090CB" },
        { val: "2", label: "Open Blockers", color: "#d64f2d" },
      ];

  const miles = isVi
    ? [
        { done: true, label: "✓ Plan phê duyệt" },
        { done: true, label: "✓ Tài liệu indexed" },
        { done: true, label: "✓ Xác nhận chính sách" },
        { active: true, label: "⏳ Checklist nhiệm vụ (4/6)" },
        { label: "○ Hoàn tất Onboarding" },
      ]
    : [
        { done: true, label: "✓ Plan Approved" },
        { done: true, label: "✓ Documents Indexed" },
        { done: true, label: "✓ Policy Acknowledged" },
        { active: true, label: "⏳ Task Checklist (4/6)" },
        { label: "○ Onboarding Completed" },
      ];

  return (
    <div className={styles.dashMockup}>
      <div className={styles.dashHead}>
        <strong>PM Dashboard</strong>
        <span className={styles.dashProject}>FURNISTORE</span>
      </div>
      <div className={styles.dashKpis}>
        {kpis.map((k) => (
          <div className={styles.dashKpi} key={k.label}>
            <span style={{ color: k.color }}>{k.val}</span>
            <small>{k.label}</small>
          </div>
        ))}
      </div>
      <div className={styles.dashMiles}>
        {miles.map((m, i) => (
          <div
            className={`${styles.dashMile} ${m.done ? styles.mileDone : ""} ${m.active ? styles.mileActive : ""}`}
            key={i}
          >
            {m.label}
          </div>
        ))}
      </div>
      <div className={styles.dashBar}>
        <div style={{ width: "67%" }} />
      </div>
    </div>
  );
}

/* ─── Main component ─────────────────────────────────────────── */
export function LandingPage() {
  const locale = useLocale();
  const tLogin = useTranslations("login");
  const tCommon = useTranslations("common");
  const [videoOpen, setVideoOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<"hero" | "how" | "roles">("hero");
  const pendingNavTarget = useRef<"hero" | "how" | "roles" | null>(null);

  const isVi = locale === "vi";

  /* Direct copy object to guarantee instant refresh and zero stale caching */
  const content = isVi
    ? {
        navWhatWeDo: "Ralion làm gì",
        navHowItWorks: "Cách hoạt động",
        navRoles: "Vai trò",
        navLogin: "Đăng nhập",
        heroLine1: "Giúp mọi kỹ sư",
        heroLine2: "hiểu đội ngũ nhanh hơn",
        heroDesc:
          "Tăng tốc onboarding kỹ thuật bằng cách kết nối repository, tài liệu dự án và quy ước đội ngũ thành một mạng tri thức tương tác. Không còn phải lần tìm trong những wiki lỗi thời.",
        btnExplore: "Khám phá Ralion",
        btnHowItWorks: "Xem cách hoạt động",
        promiseGrounded: "Câu trả lời kèm nguồn",
        promisePersonalized: "Lộ trình theo từng dự án",
        watchDemo: "Xem video Ralion hoạt động",
        watchDemoHint: "Video demo sản phẩm · xem ngay tại đây",
        svcPlanTitle: "Lộ trình onboarding",
        svcPlanSub: "PM tạo & phê duyệt kế hoạch",
        svcChatTitle: "RAG Chat thông minh",
        svcChatSub: "Trả lời kèm citation xác thực",
        svcDocsTitle: "Quản lý tài liệu",
        svcDocsSub: "Upload và phân loại tự động",
        svcTrackTitle: "Theo dõi tiến độ",
        svcTrackSub: "Checklist & quản lý Blocker",
        introHeading: "Rút ngắn thời gian từ ngày đầu đến đóng góp đầu tiên.",
        introText:
          "Ralion kết nối codebase, tài liệu dự án và quy ước đội ngũ thành một hành trình onboarding có thứ tự, có nguồn, có người chịu trách nhiệm — thay thế wiki rải rác và hỗ trợ 1:1 lặp lại.",
        f1Label: "Sinh kế hoạch bằng AI",
        f1Sub: "PM tạo và duyệt lộ trình",
        f1TitleAccent: "Candidate Plan",
        f1TitleRest: "được AI viết chi tiết từ tài liệu thật.",
        f1Body:
          "PM chọn Engineer, AI đọc toàn bộ tài liệu dự án và sinh ra lộ trình hoàn chỉnh — mỗi task có mục tiêu, các bước thực hiện, kết quả cần đạt và trích dẫn nguồn xác thực.",
        f2Label: "RAG Chat có nguồn",
        f2Sub: "Kỹ sư hỏi — AI trả lời đúng",
        f2TitlePre: "Câu trả lời dẫn ngược về",
        f2TitleAccent: "tài liệu thật",
        f2TitlePost: "và chính sách công ty.",
        f2Body:
          "Kỹ sư có thể hỏi bất kỳ thắc mắc nào — từ tài liệu dự án được cấp quyền truy cập, chính sách công ty (HR, IT, Security) đến quy ước làm việc. Ralion trả lời kèm trích dẫn nguồn (citation) trỏ về đúng đoạn văn trong tài liệu đã phê duyệt. Không bịa đặt, không mơ hồ.",
        f3Label: "Theo dõi và đóng onboarding",
        f3Sub: "PM kiểm soát toàn bộ hành trình",
        f3TitlePre: "Từ",
        f3TitleAccent: "Lộ trình phê duyệt",
        f3TitlePost: "tới Hoàn tất nhiệm vụ — mọi thứ trong tầm tay.",
        f3Body:
          "PM theo dõi tiến độ checklist của từng kỹ sư theo milestone, nhận cảnh báo khi có Blocker, hỗ trợ tháo gỡ kịp thời và xác nhận hoàn thành onboarding. Kỹ sư luôn nắm rõ từng bước cần làm mà không bị bỡ ngỡ.",
        rolesTitle: "Giá trị cho từng vai trò",
        rolesLead: "Được xây dựng cho mọi thành viên trong tổ chức kỹ thuật.",
        rolesFlow: "Từ thiết lập tổ chức đến đóng góp đầu tiên",
        rolePmTitle: "Project Manager (PM)",
        rolePmBody:
          "Kết nối GitHub, quản lý và phân loại tài liệu dự án, duyệt onboarding plan do AI sinh, theo dõi tiến độ, blocker và các quy ước được khai phá từ review.",
        rolePmCta: "Khám phá cổng PM",
        roleEngTitle: "Kỹ sư mới (Engineer)",
        roleEngBody:
          "Nhận checklist theo đúng dự án và vai trò, hỏi RAG Chat trên tài liệu được cấp quyền, đọc chính sách, xem convention, cập nhật nhiệm vụ và báo blocker cho PM.",
        roleEngCta: "Khám phá cổng Kỹ sư",
        roleHrTitle: "Nhân sự (HR)",
        roleHrBody:
          "Quản lý thư viện chính sách HR/IT/Security, đưa tài liệu vào knowledge base và theo dõi việc đọc, xác nhận chính sách của từng nhân sự.",
        roleHrCta: "Khám phá cổng HR",
        roleAdminTitle: "Quản trị viên (Admin)",
        roleAdminBody:
          "Quản lý người dùng, dự án và membership; phân vai trò hệ thống, cấp hoặc thu hồi quyền truy cập và duy trì master onboarding template dùng chung.",
        roleAdminCta: "Khám phá cổng Admin",
        techTitle: "Được xây dựng trên nền tảng đáng tin cậy",
        nlHeading: "Sẵn sàng rút ngắn thời gian onboarding?",
        nlText: "Đăng nhập và thiết lập dự án đầu tiên ngay hôm nay.",
        nlCta: "Đăng nhập Ralion",
        footerTagline: "Trợ lý onboarding theo dự án dành cho đội ngũ kỹ thuật.",
        footerEmail: "ralion@transformerlabs.ai",
        footerAboutTitle: "Về Ralion",
        footerContactTitle: "Liên hệ",
        footerTeam: "Đội ngũ VinUni AI20K",
        footerCohort: "Build Phase Cohort 3 · 2026",
        footerFollowTitle: "Theo dõi",
        footerFeatures: "Tính năng",
        copyright: "© 2026 Ralion. Đã đăng ký bản quyền.",
      }
    : {
        navWhatWeDo: "What We Do",
        navHowItWorks: "How It Works",
        navRoles: "Roles",
        navLogin: "Sign In",
        heroLine1: "Help Every Engineer",
        heroLine2: "Understand Teams Faster",
        heroDesc:
          "Accelerate technical onboarding by connecting repositories, project documents, and team conventions into an interactive knowledge network.",
        btnExplore: "Explore Ralion",
        btnHowItWorks: "See How It Works",
        promiseGrounded: "Source-grounded answers",
        promisePersonalized: "Project-scoped roadmaps",
        watchDemo: "Watch Ralion in action",
        watchDemoHint: "Product demo · watch without leaving this page",
        svcPlanTitle: "Onboarding Roadmap",
        svcPlanSub: "PM creates & approves plans",
        svcChatTitle: "Intelligent RAG Chat",
        svcChatSub: "Source-grounded citations",
        svcDocsTitle: "Document Hub",
        svcDocsSub: "Auto indexing & tagging",
        svcTrackTitle: "Progress Tracking",
        svcTrackSub: "Checklists & Blockers",
        introHeading: "Shorten the time from day one to first contribution.",
        introText:
          "Ralion connects codebase, project documents, and team conventions into a structured, source-grounded onboarding journey.",
        f1Label: "AI Plan Generation",
        f1Sub: "PM creates & approves the roadmap",
        f1TitleAccent: "Candidate Plan",
        f1TitleRest: "written in detail by AI from real documents.",
        f1Body:
          "PM selects an engineer, AI analyzes project documentation and generates a comprehensive roadmap — each task includes goals, steps, expected deliverables, and verified source citations.",
        f2Label: "Source-grounded RAG Chat",
        f2Sub: "Ask questions — AI answers accurately",
        f2TitlePre: "Answers directly cited from",
        f2TitleAccent: "real project docs",
        f2TitlePost: "and company policies.",
        f2Body:
          "Engineers can ask any question — from accessible project docs, company policies (HR, IT, Security) to team conventions. Ralion provides answers with direct citations to verified documentation. No hallucinations, no ambiguity.",
        f3Label: "Progress Tracking & Completion",
        f3Sub: "Full visibility across milestones",
        f3TitlePre: "From",
        f3TitleAccent: "Approved Roadmap",
        f3TitlePost: "to Onboarding Completion — everything in reach.",
        f3Body:
          "PM tracks milestone progress, receives instant blocker alerts, resolves obstacles in time, and confirms onboarding completion. Engineers always know their next step with clarity.",
        rolesTitle: "Value for Every Role",
        rolesLead: "Built for every contributor in technical organizations.",
        rolesFlow: "From workspace setup to the first contribution",
        rolePmTitle: "Project Manager (PM)",
        rolePmBody:
          "Connect GitHub, curate project documents, approve AI-generated onboarding plans, and monitor progress, blockers, and mined team conventions.",
        rolePmCta: "Explore PM Portal",
        roleEngTitle: "Software Engineer",
        roleEngBody:
          "Follow a project-specific checklist, query authorized knowledge through RAG Chat, read policies and conventions, update tasks, and report blockers.",
        roleEngCta: "Explore Engineer Portal",
        roleHrTitle: "Human Resources (HR)",
        roleHrBody:
          "Manage the HR/IT/Security policy library, ingest approved documents into the knowledge base, and track employee acknowledgements.",
        roleHrCta: "Explore HR Portal",
        roleAdminTitle: "System Admin",
        roleAdminBody:
          "Manage users, projects, and memberships; assign system roles, grant or revoke access, and maintain the shared master onboarding template.",
        roleAdminCta: "Explore Admin Portal",
        techTitle: "Built on trusted foundations",
        nlHeading: "Ready to shorten onboarding time?",
        nlText: "Sign in and set up your first project today.",
        nlCta: "Sign In to Ralion",
        footerTagline: "Project onboarding assistant for technical engineering teams.",
        footerEmail: "ralion@transformerlabs.ai",
        footerAboutTitle: "About Ralion",
        footerContactTitle: "Contact",
        footerTeam: "VinUni AI20K Team",
        footerCohort: "Build Phase Cohort 3 · 2026",
        footerFollowTitle: "Follow Us",
        footerFeatures: "Features",
        copyright: "© 2026 Ralion. All rights reserved.",
      };

  /* Escape to close video modal */
  useEffect(() => {
    if (!videoOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setVideoOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [videoOpen]);

  useEffect(() => {
    const updateActiveSection = () => {
      // Treat the section occupying the upper reading zone as active. A fixed
      // 150px marker caused smooth-scroll to overwrite the clicked nav item
      // before a tall section heading reached the sticky header.
      const readingZone = Math.max(170, Math.min(window.innerHeight * 0.38, 380));
      const marker = window.scrollY + readingZone;
      const pageTop = (id: string) => {
        const element = document.getElementById(id);
        return element ? element.getBoundingClientRect().top + window.scrollY : Number.POSITIVE_INFINITY;
      };
      const rolesTop = pageTop("roles");
      const howTop = pageTop("how");
      if (pendingNavTarget.current) {
        const pending = pendingNavTarget.current;
        const target = document.getElementById(pending);
        const arrived = pending === "hero"
          ? window.scrollY < 24
          : Boolean(target && target.getBoundingClientRect().top <= readingZone);
        if (!arrived) return;
        pendingNavTarget.current = null;
      }
      setActiveSection(marker >= rolesTop ? "roles" : marker >= howTop ? "how" : "hero");
    };
    updateActiveSection();
    window.addEventListener("scroll", updateActiveSection, { passive: true });
    window.addEventListener("resize", updateActiveSection);
    return () => {
      window.removeEventListener("scroll", updateActiveSection);
      window.removeEventListener("resize", updateActiveSection);
    };
  }, []);

  /* Scroll reveal with IntersectionObserver */
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) e.target.classList.add(styles.visible);
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -30px 0px" },
    );
    document.querySelectorAll("[data-aos]").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  /* Services data */
  const services = [
    {
      icon: <LayoutList size={24} />,
      color: "#4628A4",
      bg: "#EFEAFF",
      title: content.svcPlanTitle,
      sub: content.svcPlanSub,
    },
    {
      icon: <MessageSquare size={24} />,
      color: "#5FC400",
      bg: "#ECFFDA",
      title: content.svcChatTitle,
      sub: content.svcChatSub,
    },
    {
      icon: <FileText size={24} />,
      color: "#0057B8",
      bg: "#DAE6FF",
      title: content.svcDocsTitle,
      sub: content.svcDocsSub,
    },
    {
      icon: <CheckSquare size={24} />,
      color: "#BB3800",
      bg: "#FFE5DA",
      title: content.svcTrackTitle,
      sub: content.svcTrackSub,
    },
  ] as const;

  /* Feature sections */
  const features = [
    {
      icon: <Sparkles size={18} />,
      iconBg: "#08D3BB",
      label: content.f1Label,
      sub: content.f1Sub,
      title: (
        <>
          <span className={styles.accent}>{content.f1TitleAccent}</span>{" "}
          {content.f1TitleRest}
        </>
      ),
      body: content.f1Body,
      media: <PlanMockup locale={locale} />,
      reverse: false,
    },
    {
      icon: <MessageSquare size={18} />,
      iconBg: "#1090CB",
      label: content.f2Label,
      sub: content.f2Sub,
      title: (
        <>
          {content.f2TitlePre}{" "}
          <span className={styles.accent}>{content.f2TitleAccent}</span>{" "}
          {content.f2TitlePost}
        </>
      ),
      body: content.f2Body,
      media: <AppMockup locale={locale} />,
      reverse: true,
    },
    {
      icon: <BarChart3 size={18} />,
      iconBg: "#7C3AED",
      label: content.f3Label,
      sub: content.f3Sub,
      title: (
        <>
          {content.f3TitlePre}{" "}
          <span className={styles.accent}>{content.f3TitleAccent}</span>{" "}
          {content.f3TitlePost}
        </>
      ),
      body: content.f3Body,
      media: <DashMockup locale={locale} />,
      reverse: false,
    },
  ] as const;

  /* 4 Specialized roles */
  const roles = [
    {
      icon: <ShieldCheck size={22} />,
      color: "#D95D00",
      bg: "#FFF2E8",
      tag: "01 · Workspace",
      title: content.roleAdminTitle,
      body: content.roleAdminBody,
      cta: content.roleAdminCta,
    },
    {
      icon: <Users size={22} />,
      color: "#7C3AED",
      bg: "#F3EEFF",
      tag: "02 · People & Policy",
      title: content.roleHrTitle,
      body: content.roleHrBody,
      cta: content.roleHrCta,
    },
    {
      icon: <Map size={22} />,
      color: "#1090CB",
      bg: "#E6F4FF",
      tag: "03 · Project & Plan",
      title: content.rolePmTitle,
      body: content.rolePmBody,
      cta: content.rolePmCta,
    },
    {
      icon: <Code2 size={22} />,
      color: "#08A995",
      bg: "#E6FBF7",
      tag: "04 · Onboarding",
      title: content.roleEngTitle,
      body: content.roleEngBody,
      cta: content.roleEngCta,
    },
  ] as const;

  const techStack = [
    { name: "Next.js 16", detail: "Web experience", iconUrl: "https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/nextjs/nextjs-original.svg" },
    { name: "FastAPI", detail: "Async API", iconUrl: "https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/fastapi/fastapi-original.svg" },
    { name: "LangGraph", detail: "AI orchestration", icon: <Workflow size={23} /> },
    { name: "PostgreSQL", detail: "System of record", iconUrl: "https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/postgresql/postgresql-original.svg" },
    { name: "pgvector + ParadeDB", detail: "Hybrid retrieval", icon: <Database size={23} /> },
    { name: "BGE-M3", detail: "Multilingual embeddings", icon: <Sparkles size={23} /> },
    { name: "Cloudinary", detail: "Document storage", icon: <Cloud size={23} /> },
    { name: "Docker", detail: "Reproducible runtime", icon: <Container size={23} /> },
  ] as const;

  const footerLinks = [
    { label: content.footerFeatures, href: "#how" },
    { label: content.navHowItWorks, href: "#how" },
    { label: content.navRoles, href: "#roles" },
    { label: content.navLogin, href: "/login" },
  ] as const;

  return (
    <div className={styles.page}>
      {/* ─── HEADER ─── */}
      <header className={styles.header}>
        <nav className={styles.nav} aria-label={content.navWhatWeDo}>
          {/* Logo */}
          <span className={styles.brand}>
            <RalionBrand href="/#hero" size={28} />
          </span>

          {/* Center nav */}
          <div className={styles.navLinks}>
            <Link aria-current={activeSection === "hero" ? "page" : undefined} className={`${styles.navLinkItem} ${activeSection === "hero" ? styles.navLinkActive : ""}`} href="/#hero" onClick={() => { pendingNavTarget.current = "hero"; setActiveSection("hero"); }}>
              {content.navWhatWeDo}
            </Link>
            <a aria-current={activeSection === "how" ? "page" : undefined} className={`${styles.navLinkItem} ${activeSection === "how" ? styles.navLinkActive : ""}`} href="#how" onClick={() => { pendingNavTarget.current = "how"; setActiveSection("how"); }}>
              {content.navHowItWorks}
            </a>
            <a aria-current={activeSection === "roles" ? "page" : undefined} className={`${styles.navLinkItem} ${activeSection === "roles" ? styles.navLinkActive : ""}`} href="#roles" onClick={() => { pendingNavTarget.current = "roles"; setActiveSection("roles"); }}>
              {content.navRoles}
            </a>
          </div>

          {/* Right */}
          <div className={styles.navRight}>
            <LanguageSwitcher className={styles.langSwitch} compact />
            <Link className={styles.loginBtn} href="/login">
              {content.navLogin}
            </Link>
          </div>
        </nav>
      </header>

      <main>
        {/* ─── HERO ─── */}
        <section className={styles.hero} id="hero">
          {/* Decorative blobs */}
          <span aria-hidden className={`${styles.blob} ${styles.blobTL}`} />
          <span aria-hidden className={`${styles.blob} ${styles.blobBR}`} />

          <div className={styles.heroInner}>
            {/* Left copy */}
            <div
              className={`${styles.heroCopy} ${styles.animUp}`}
              data-aos=""
            >
              <h1>
                <span>{content.heroLine1} </span>
                <span className={styles.heroAccent}>{content.heroLine2}.</span>
              </h1>

              <p className={styles.heroDesc}>{content.heroDesc}</p>

              <div className={styles.heroBtns}>
                <Link className={styles.btnPrimary} href="/login">
                  {content.btnExplore}
                  <ArrowRight size={16} />
                </Link>
                <a className={styles.btnOutline} href="#how">
                  <Play size={14} className={styles.playIcon} />
                  {content.btnHowItWorks}
                </a>
              </div>

              <ul className={styles.heroChecks}>
                <li>
                  <Check size={14} className={styles.checkIcon} />
                  {content.promiseGrounded}
                </li>
                <li>
                  <Check size={14} className={styles.checkIcon} />
                  {content.promisePersonalized}
                </li>
              </ul>

              {/* Video demo card matching login page style */}
              <button
                className={styles.videoButton}
                onClick={() => setVideoOpen(true)}
                type="button"
              >
                <span className={styles.videoArtwork} aria-hidden="true">
                  <span className={styles.videoWindowBar}>
                    <i />
                    <i />
                    <i />
                  </span>
                  <span className={styles.videoMockContent}>
                    <i />
                    <i />
                    <i />
                    <i />
                  </span>
                  <span className={styles.playIconCenter}>
                    <Play size={18} fill="#1090CB" />
                  </span>
                </span>
                <span className={styles.videoMeta}>
                  <span>
                    <strong>{content.watchDemo}</strong>
                    <small>{content.watchDemoHint}</small>
                  </span>
                  <ArrowRight className={styles.videoArrowIcon} size={18} />
                </span>
              </button>
            </div>

            {/* Right visual */}
            <div
              className={`${styles.heroVisual} ${styles.animRight}`}
              data-aos=""
            >
              <AppMockup locale={locale} />

              {/* Float progress card */}
              <div className={styles.floatProgress}>
                <Map size={14} className={styles.floatIcon} />
                <div>
                  <span>{isVi ? "LỘ TRÌNH TUẦN ĐẦU" : "FIRST WEEK ROADMAP"}</span>
                  <strong>{isVi ? "4/6 nhiệm vụ hoàn tất" : "4/6 tasks completed"}</strong>
                </div>
                <div className={styles.ringWrap}>
                  <svg className={styles.ring} viewBox="0 0 36 36">
                    <circle className={styles.ringBg} cx="18" cy="18" r="15" />
                    <circle
                      className={styles.ringFill}
                      cx="18"
                      cy="18"
                      r="15"
                      strokeDasharray="67 100"
                    />
                    <text className={styles.ringText} x="18" y="21">67%</text>
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ─── SERVICES ─── */}
        <section className={styles.servicesSection} id="what-we-do">
          <div className={styles.servicesGrid}>
            {services.map((svc, i) => (
              <div
                className={`${styles.svcCard} ${styles.animUp}`}
                data-aos=""
                key={svc.title}
                style={{ transitionDelay: `${i * 70}ms` }}
              >
                <span
                  className={styles.svcIcon}
                  style={{ background: svc.bg, color: svc.color }}
                >
                  {svc.icon}
                </span>
                <div className={styles.svcText}>
                  <strong>{svc.title}</strong>
                  <span>{svc.sub}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ─── INTRO (HOW IT WORKS START) ─── */}
        <section className={styles.introSection} id="how">
          <div
            className={`${styles.introInner} ${styles.animUp}`}
            data-aos=""
          >
            <h2>{content.introHeading}</h2>
            <p>{content.introText}</p>
          </div>
        </section>

        {/* ─── FEATURE SECTIONS ─── */}
        <section className={styles.featuresSection}>
          {features.map((feat, i) => (
            <div
              className={`${styles.featRow} ${feat.reverse ? styles.featReverse : ""} ${styles.animUp}`}
              data-aos=""
              key={i}
              style={{ transitionDelay: "50ms" }}
            >
              {/* Copy */}
              <div className={styles.featCopy}>
                <div className={styles.featLabel}>
                  <span
                    className={styles.featIconBadge}
                    style={{ background: `${feat.iconBg}22`, color: feat.iconBg }}
                  >
                    {feat.icon}
                  </span>
                  <div>
                    <strong>{feat.label}</strong>
                    <small>{feat.sub}</small>
                  </div>
                </div>
                <h3>{feat.title}</h3>
                <p>{feat.body}</p>
              </div>

              {/* Media */}
              <div className={styles.featMedia}>{feat.media}</div>
            </div>
          ))}
        </section>

        {/* ─── ROLE FLOW ─── */}
        <section className={styles.rolesSection}>
          <div className={`${styles.rolesHeader} ${styles.animUp}`} data-aos="" id="roles">
            <h2>{content.rolesTitle}</h2>
            <p>{content.rolesLead}</p>
            <span className={styles.rolesFlowLabel}>{content.rolesFlow}</span>
          </div>

          <div aria-label={content.rolesFlow} className={styles.rolesGrid}>
            {roles.map((r, i) => (
              <article
                className={`${styles.roleCard} ${styles.animUp}`}
                data-aos=""
                key={r.title}
                style={{ transitionDelay: `${i * 60}ms` }}
              >
                <div className={styles.roleCardTop}>
                  <span
                    className={styles.roleIconWrap}
                    style={{ background: r.bg, color: r.color }}
                  >
                    {r.icon}
                  </span>
                  <span
                    className={styles.roleTag}
                    style={{ color: r.color, background: r.bg }}
                  >
                    {r.tag}
                  </span>
                </div>
                <h3>{r.title}</h3>
                <p>{r.body}</p>
                <Link className={styles.roleBtn} href="/login">
                  {r.cta} <ArrowRight size={14} />
                </Link>
              </article>
            ))}
          </div>
        </section>

        {/* ─── TECH STACK ─── */}
        <section className={styles.techSection}>
          <p className={`${styles.techTitle} ${styles.animUp}`} data-aos="">
            {content.techTitle}
          </p>
          <div className={`${styles.techRow} ${styles.animUp}`} data-aos="">
            {techStack.map((item) => (
              <article className={styles.techBadge} key={item.name}>
                <span className={styles.techIcon}>
                  {"iconUrl" in item ? <span aria-hidden="true" className={styles.techBrandIcon} style={{ backgroundImage: `url(${item.iconUrl})` }} /> : item.icon}
                </span>
                <span><strong>{item.name}</strong><small>{item.detail}</small></span>
              </article>
            ))}
          </div>
        </section>

        {/* ─── NEWSLETTER ─── */}
        <section className={styles.nlSection}>
          <div className={`${styles.nlInner} ${styles.animUp}`} data-aos="">
            <h2>{content.nlHeading}</h2>
            <p>{content.nlText}</p>
            <Link className={styles.btnPrimaryLg} href="/login">
              {content.nlCta} <ArrowRight size={16} />
            </Link>
          </div>
        </section>
      </main>

      {/* ─── FOOTER ─── */}
      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          {/* Brand */}
          <div className={styles.footerBrand}>
            <span className={styles.footerLogo}>Ralion</span>
            <p>{content.footerTagline}</p>
            <a
              className={styles.footerMail}
              href={`mailto:${content.footerEmail}`}
            >
              <Mail size={13} />
              {content.footerEmail}
            </a>
          </div>

          {/* About links */}
          <div className={styles.footerCol}>
            <strong>{content.footerAboutTitle}</strong>
            {footerLinks.map((l) => (
              <a href={l.href} key={l.label}>
                {l.label}
              </a>
            ))}
          </div>

          {/* Contact */}
          <div className={styles.footerCol}>
            <strong>{content.footerContactTitle}</strong>
            <p>{content.footerTeam}</p>
            <span>{content.footerCohort}</span>
          </div>

          {/* Social */}
          <div className={styles.footerSocial}>
            <strong>{content.footerFollowTitle}</strong>
            <div className={styles.socialRow}>
              {[
                { icon: <Globe size={15} />, href: "#" },
                { icon: <ExternalLink size={15} />, href: "#" },
                { icon: <Code2 size={15} />, href: "#" },
              ].map((s, i) => (
                <a className={styles.socialBtn} href={s.href} key={i}>
                  {s.icon}
                </a>
              ))}
            </div>
          </div>
        </div>

        <div className={styles.footerBottom}>
          <span>{content.copyright}</span>
        </div>
      </footer>

      {/* ─── VIDEO DEMO MODAL ─── */}
      {videoOpen && (
        <div
          className={styles.videoOverlay}
          role="presentation"
          onMouseDown={() => setVideoOpen(false)}
        >
          <section
            aria-labelledby="demo-video-title"
            aria-modal="true"
            className={styles.videoModal}
            onMouseDown={(e) => e.stopPropagation()}
            role="dialog"
          >
            <header className={styles.videoModalHeader}>
              <div>
                <span className={styles.videoModalEyebrow}>{tLogin("videoEyebrow")}</span>
                <h2 id="demo-video-title" className={styles.videoModalTitle}>{tLogin("videoTitle")}</h2>
              </div>
              <button
                aria-label={tCommon("close")}
                className={styles.videoCloseBtn}
                onClick={() => setVideoOpen(false)}
                type="button"
              >
                <X size={20} />
              </button>
            </header>
            <div className={styles.videoFrame}>
              <iframe
                allow="autoplay; encrypted-media; picture-in-picture"
                allowFullScreen
                loading="eager"
                src={RALION_DEMO_VIDEO_URL}
                title={tLogin("videoTitle")}
              />
            </div>
            <p className={styles.videoCaption}>{tLogin("videoDescription")}</p>
          </section>
        </div>
      )}
    </div>
  );
}
