/**
 * Test cho helper xử lý giờ UTC-không-offset mà backend trả về (xem docstring `formatDateTime.ts`
 * để hiểu vì sao cần chuyển đổi thủ công thay vì tin `new Date(string)`).
 *
 * Chạy test trong 2 múi giờ hệ điều hành KHÁC NHAU (UTC và Asia/Ho_Chi_Minh) để chứng minh kết quả
 * KHÔNG phụ thuộc múi giờ máy chạy test — đúng bug gốc: `new Date()` mặc định ăn theo giờ OS.
 */
import { afterEach, describe, expect, it } from "vitest";

import {
  backendStringToVietnamLocalInput,
  formatDateTime,
  recommendedPlanStartVietnamLocal,
  vietnamLocalInputToBackendString,
} from "../formatDateTime";

describe("formatDateTime", () => {
  it("cộng đúng 7 tiếng khi hiển thị — giờ UTC backend trả về phải thành giờ Việt Nam", () => {
    // Đúng số liệu PM báo lỗi: backend trả "02:47" (UTC), phải hiện "09:47" (VN).
    expect(formatDateTime("2026-08-19T02:47:00")).toBe("09:47 19/08/2026");
  });

  it("xử lý đúng khi giờ UTC cộng 7 tiếng tràn sang ngày hôm sau", () => {
    expect(formatDateTime("2026-08-19T20:00:00")).toBe("03:00 20/08/2026");
  });

  it("trả về dấu gạch ngang khi không có giá trị", () => {
    expect(formatDateTime(null)).toBe("—");
  });

  it("không bị ảnh hưởng nếu chuỗi ĐÃ có offset (Z) — không cộng thêm 'Z' lần 2", () => {
    expect(formatDateTime("2026-08-19T02:47:00Z")).toBe("09:47 19/08/2026");
  });
});

describe("vietnamLocalInputToBackendString", () => {
  it("PM nhập 09:00 giờ VN -> backend phải nhận 02:00 UTC", () => {
    expect(vietnamLocalInputToBackendString("2026-08-24T09:00")).toBe("2026-08-24T02:00:00");
  });

  it("giờ VN đầu ngày (00:00-06:59) lùi UTC về NGÀY HÔM TRƯỚC", () => {
    expect(vietnamLocalInputToBackendString("2026-08-24T02:00")).toBe("2026-08-23T19:00:00");
  });

  it("chuỗi không đúng định dạng thì trả về null thay vì NaN/Invalid Date âm thầm", () => {
    expect(vietnamLocalInputToBackendString("không phải ngày giờ")).toBeNull();
    expect(vietnamLocalInputToBackendString("")).toBeNull();
  });
});

describe("backendStringToVietnamLocalInput", () => {
  it("chiều ngược lại đúng — pre-fill input từ due_at backend", () => {
    expect(backendStringToVietnamLocalInput("2026-08-24T02:00:00")).toBe("2026-08-24T09:00");
  });

  it("null/rỗng thì trả về chuỗi rỗng (input để trống, không lỗi)", () => {
    expect(backendStringToVietnamLocalInput(null)).toBe("");
  });
});

describe("round-trip: input VN -> backend -> hiển thị lại đúng như PM đã gõ", () => {
  const cases = ["2026-08-24T09:00", "2026-08-01T00:15", "2026-12-31T23:59", "2026-08-24T02:00"];

  for (const input of cases) {
    it(`round-trip giữ nguyên: ${input}`, () => {
      const backendValue = vietnamLocalInputToBackendString(input);
      expect(backendValue).not.toBeNull();
      expect(backendStringToVietnamLocalInput(backendValue)).toBe(input);
    });
  }
});

describe("kết quả không phụ thuộc múi giờ hệ điều hành máy chạy test", () => {
  const originalTZ = process.env.TZ;

  afterEach(() => {
    process.env.TZ = originalTZ;
  });

  for (const tz of ["UTC", "America/New_York", "Asia/Tokyo"]) {
    it(`giữ nguyên kết quả khi TZ hệ thống = ${tz}`, () => {
      process.env.TZ = tz;
      expect(formatDateTime("2026-08-19T02:47:00")).toBe("09:47 19/08/2026");
      expect(vietnamLocalInputToBackendString("2026-08-24T09:00")).toBe("2026-08-24T02:00:00");
    });
  }
});

describe("recommendedPlanStartVietnamLocal", () => {
  // Mọi mốc "now" dưới đây được viết theo giờ UTC — trừ 7 tiếng ra đúng giờ Việt Nam tương ứng.
  // 2026-08-19 là Thứ Tư.
  it("trong giờ hành chính (T4 10:00 VN) -> dùng luôn giờ hiện tại", () => {
    const now = new Date("2026-08-19T03:00:00Z"); // 10:00 VN, Thứ Tư
    expect(recommendedPlanStartVietnamLocal(now)).toBe("2026-08-19T10:00");
  });

  it("đúng ranh giới 09:00 VN -> tính là ĐÃ trong giờ hành chính", () => {
    const now = new Date("2026-08-19T02:00:00Z"); // 09:00 VN đúng
    expect(recommendedPlanStartVietnamLocal(now)).toBe("2026-08-19T09:00");
  });

  it("đúng ranh giới 17:00 VN -> tính là NGOÀI giờ hành chính (đã hết giờ)", () => {
    const now = new Date("2026-08-19T10:00:00Z"); // 17:00 VN đúng, Thứ Tư
    expect(recommendedPlanStartVietnamLocal(now)).toBe("2026-08-20T09:00");
  });

  it("trước giờ hành chính cùng ngày làm việc (T4 06:00 VN) -> nhảy tới 09:00 CÙNG NGÀY", () => {
    const now = new Date("2026-08-18T23:00:00Z"); // 06:00 VN ngày 19/08 (Thứ Tư)
    expect(recommendedPlanStartVietnamLocal(now)).toBe("2026-08-19T09:00");
  });

  it("sau giờ hành chính (T4 20:00 VN) -> nhảy tới 09:00 ngày làm việc kế tiếp (Thứ Năm)", () => {
    const now = new Date("2026-08-19T13:00:00Z"); // 20:00 VN, Thứ Tư
    expect(recommendedPlanStartVietnamLocal(now)).toBe("2026-08-20T09:00");
  });

  it("bấm vào Thứ Sáu tối -> nhảy qua T7+CN, ra đúng Thứ Hai 09:00", () => {
    const now = new Date("2026-08-21T14:00:00Z"); // 21:00 VN, Thứ Sáu 21/08
    expect(recommendedPlanStartVietnamLocal(now)).toBe("2026-08-24T09:00");
  });

  it("bấm vào giữa trưa Thứ Bảy -> vẫn nhảy tới Thứ Hai 09:00, không phải Chủ Nhật", () => {
    const now = new Date("2026-08-22T05:00:00Z"); // 12:00 VN, Thứ Bảy 22/08
    expect(recommendedPlanStartVietnamLocal(now)).toBe("2026-08-24T09:00");
  });

  it("bấm vào rạng sáng Chủ Nhật -> nhảy tới Thứ Hai 09:00", () => {
    const now = new Date("2026-08-23T00:30:00Z"); // 07:30 VN, Chủ Nhật 23/08
    expect(recommendedPlanStartVietnamLocal(now)).toBe("2026-08-24T09:00");
  });

  it("nhảy ngày làm việc kế tiếp phải xử lý đúng khi tràn sang THÁNG mới", () => {
    // 2026-08-31 là Thứ Hai — bấm tối muộn thì ngày làm việc kế tiếp là Thứ Ba 01/09.
    const now = new Date("2026-08-31T13:00:00Z"); // 20:00 VN, Thứ Hai 31/08
    expect(recommendedPlanStartVietnamLocal(now)).toBe("2026-09-01T09:00");
  });
});
