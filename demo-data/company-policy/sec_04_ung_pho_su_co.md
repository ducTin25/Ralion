# Chính sách Ứng phó Sự cố An toàn Thông tin (Incident Response)

- **Mã tài liệu:** SEC-POL-004
- **Phiên bản:** 3.2 — Ngày hiệu lực: 01/01/2026
- **Bộ phận ban hành:** Phòng An toàn Thông tin
- **Phạm vi áp dụng:** Mọi sự cố an toàn thông tin liên quan hệ thống, dữ liệu, con người của công ty
- **Tài liệu tham chiếu:** NIST SP 800-61r2; ISO/IEC 27035; IT-POL-005 (Sự cố hạ tầng)

## 1. Mục đích

Đảm bảo sự cố an toàn thông tin được phát hiện, báo cáo, ngăn chặn và khắc phục nhanh nhất, giảm thiểu thiệt hại và đáp ứng nghĩa vụ pháp lý về thông báo sự cố.

## 2. Thế nào là sự cố an toàn thông tin

Bao gồm nhưng không giới hạn:

- Tài khoản bị chiếm đoạt hoặc đăng nhập trái phép.
- Nhiễm mã độc, ransomware, hành vi bất thường trên máy.
- Email lừa đảo (**phishing**) — kể cả khi bạn *chưa* click.
- Lộ/rò rỉ dữ liệu: gửi nhầm dữ liệu Confidential ra ngoài, chia sẻ sai quyền, dữ liệu xuất hiện nơi công khai.
- Lộ secret/API key (xử lý phối hợp SEC-POL-003).
- Mất thiết bị chứa dữ liệu công ty.
- Tấn công có chủ đích: dò quét, khai thác lỗ hổng, DDoS, thay đổi trái phép hệ thống.
- Vi phạm nội bộ: truy cập vượt quyền có chủ đích, sao chép dữ liệu bất thường trước khi nghỉ việc.

**Nguyên tắc: nghi ngờ là báo.** Báo nhầm không bị phê bình; không báo mới là vi phạm.

## 3. Báo cáo sự cố — nghĩa vụ của mọi nhân viên

- **Thời hạn: trong vòng 1 giờ** kể từ khi phát hiện hoặc nghi ngờ.
- Kênh báo: nút "Report Phishing" trên email; kênh khẩn cấp #security-incident; hotline Security (24/7 cho mức nghiêm trọng); ticket Security cho mức thấp.
- Nội dung: điều gì xảy ra, khi nào, trên máy/hệ thống nào, đã thao tác gì.
- **Giữ nguyên hiện trường:** không tắt máy (trừ khi Security yêu cầu), không xóa email/file nghi ngờ, không tự quét/diệt, không thông báo rộng rãi khi chưa được phép — kể cả cho đồng nghiệp liên quan nếu nghi vấn nội bộ.

## 4. Phân loại mức độ

| Mức | Tiêu chí | Ví dụ |
|---|---|---|
| SEV1 — Nghiêm trọng | Xâm nhập xác nhận, lộ dữ liệu Restricted, ransomware, ảnh hưởng khách hàng | Dữ liệu khách hàng bị rao bán, production bị chiếm quyền |
| SEV2 — Cao | Xâm nhập nghi vấn cao, lộ dữ liệu Confidential phạm vi hẹp, tài khoản bị chiếm | Tài khoản nhân viên gửi mail lạ hàng loạt |
| SEV3 — Trung bình | Sự kiện đáng ngờ chưa xác nhận thiệt hại | Phishing có người click nhưng chưa nhập credential |
| SEV4 — Thấp | Sự kiện an ninh thông thường | Phishing báo cáo kịp, quét cổng từ ngoài bị chặn |

## 5. Quy trình ứng phó (6 giai đoạn)

1. **Chuẩn bị:** đội ứng phó (IRT) được chỉ định, diễn tập tối thiểu 1 lần/năm (bao gồm diễn tập ransomware và phishing toàn công ty).
2. **Phát hiện & phân tích:** Security xác minh, phân mức SEV, mở incident record; SEV1/SEV2 lập Incident Commander và kênh điều phối riêng.
3. **Ngăn chặn (Containment):** cô lập máy nhiễm khỏi mạng, khóa tài khoản, thu hồi phiên/secret, chặn IP/domain độc hại. Ngăn chặn ưu tiên hơn điều tra.
4. **Loại bỏ (Eradication):** xóa mã độc, vá lỗ hổng bị khai thác, xây lại (rebuild) hệ thống bị xâm nhập thay vì chỉ làm sạch.
5. **Khôi phục (Recovery):** đưa hệ thống trở lại từ trạng thái sạch/backup, giám sát tăng cường tối thiểu 2 tuần sau sự cố.
6. **Rút kinh nghiệm:** báo cáo blameless trong 5 ngày làm việc (SEV1/SEV2), action item có chủ và deadline, cập nhật playbook.

## 6. SLA phản hồi của Security

| Mức | Phản hồi | Cập nhật | Báo cáo lãnh đạo |
|---|---|---|---|
| SEV1 | 30 phút, 24/7 | Mỗi giờ | Ngay lập tức, Ban Giám đốc |
| SEV2 | 1 giờ | Mỗi 4 giờ | Trong ngày |
| SEV3 | 4 giờ làm việc | Hằng ngày | Báo cáo tuần |
| SEV4 | 1 ngày làm việc | Khi đóng | Báo cáo tháng |

## 7. Thông báo bên ngoài

- Chỉ **người phát ngôn được chỉ định** (Ban Giám đốc/Pháp chế) thông báo cho khách hàng, đối tác, báo chí, cơ quan chức năng. Nhân viên không tự trao đổi về sự cố ra bên ngoài, kể cả mạng xã hội.
- Sự cố liên quan dữ liệu cá nhân: Security phối hợp Pháp chế/DPO đánh giá nghĩa vụ thông báo, nội dung, đối tượng và thời hạn theo **Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15**, Nghị định 356/2025/NĐ-CP và quy định còn hiệu lực. Nhân viên không tự suy diễn hoặc tự gửi thông báo pháp lý ra bên ngoài.
- Sự cố do nhà cung cấp: kích hoạt điều khoản thông báo sự cố trong hợp đồng, yêu cầu báo cáo nguyên nhân.

## 8. Diễn tập và nâng cao nhận thức

- Diễn tập phishing nội bộ hằng quý; người click nhiều lần được đào tạo bổ sung (không kỷ luật cho diễn tập).
- Khóa nhận thức ATTT bắt buộc hằng năm (theo HR-POL-004), cập nhật theo thủ đoạn mới (deepfake, lừa đảo giọng nói, QR độc hại).

## 9. Vi phạm

- Không báo cáo sự cố đã biết, xóa dấu vết, cản trở điều tra: xử lý kỷ luật mức nghiêm trọng theo HR-POL-005.
- Người báo cáo thiện chí (kể cả tự gây ra do sơ suất và chủ động báo): được xem xét giảm nhẹ.

**Từ khóa định tuyến về Security:** sự cố bảo mật, phishing, lừa đảo, email lạ, mã độc, virus, ransomware, tài khoản bị hack, bị chiếm, đăng nhập lạ, lộ dữ liệu, rò rỉ, mất laptop, tấn công, DDoS, incident, báo cáo sự cố, deepfake.


## 10. Vai trò trong Incident Response Team

| Vai trò | Trách nhiệm chính |
|---|---|
| Incident Commander | điều phối, quyết định ưu tiên, giữ nhịp cập nhật |
| Security Lead | điều tra kỹ thuật, containment/eradication |
| IT/Service Owner | khôi phục dịch vụ, cung cấp kiến thức hệ thống |
| Legal/Privacy | nghĩa vụ pháp lý, bảo toàn hồ sơ, external notification |
| Communications | thông điệp nội bộ/khách hàng nếu được kích hoạt |
| HR | sự cố liên quan nhân sự/insider theo need-to-know |

Vai trò có thể kiêm nhiệm ở sự cố nhỏ nhưng SEV1/SEV2 nên tách điều phối khỏi người debug chính.

## 11. Evidence handling

Log, image, email, file nghi vấn và timestamp cần được bảo toàn. Ghi lại ai thu thập, thời điểm và nguồn. Không tự chạy công cụ “cleaner”, format máy hoặc xóa email trước khi Security xác nhận nếu có khả năng làm mất bằng chứng.

## 12. Containment decision

Containment cân bằng giữa ngăn thiệt hại và duy trì bằng chứng/dịch vụ. Ví dụ account compromise có thể revoke session trước khi reset toàn bộ hệ thống; endpoint nghi ransomware cần cô lập mạng nhưng không nhất thiết tắt nguồn ngay.

## 13. Playbook tối thiểu

Security duy trì playbook cho phishing/account takeover, malware/ransomware, exposed secret, lost device, data leakage, cloud compromise và vulnerability exploitation. Playbook là hướng dẫn tác nghiệp; severity và quyết định pháp lý vẫn dựa trên case thực tế.

## 14. External notification governance

Chỉ Legal/Privacy/Communications được ủy quyền mới quyết định và phát hành thông báo cho cơ quan, khách hàng, đối tác hoặc báo chí. Incident record phải ghi thời điểm phát hiện, thời điểm xác nhận, loại dữ liệu/hệ thống, phạm vi và quyết định notification để chứng minh tuân thủ.

## 15. Recovery acceptance

Recovery hoàn tất khi service owner và Security xác nhận: vector xâm nhập đã được xử lý ở mức chấp nhận được, credential cần thiết đã rotate/revoke, hệ thống được phục hồi từ trạng thái tin cậy và monitoring tăng cường đã bật.

## 16. Lessons learned

Action item được ưu tiên theo risk reduction. Mỗi item có owner, due date và acceptance evidence. Training có thể là một action nhưng không được dùng thay cho control kỹ thuật/quy trình nếu nguyên nhân gốc là control thiếu hoặc sai thiết kế.

## 17. Tabletop exercise

Tối thiểu hằng năm tổ chức tabletop cho kịch bản ảnh hưởng lớn. Team critical nên luân phiên ransomware, credential compromise, cloud outage/data breach và supply-chain incident; kết quả exercise phải tạo action item như incident thật.
