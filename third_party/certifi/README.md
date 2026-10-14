# HTTPS 根证书

随包保存 certifi 2026.7.22 的 Mozilla 公共根证书，供独立 HTTPS 订阅验证使用。
数据不包含用户证书或私钥，不从开发机的系统证书库导出。

上游：https://github.com/certifi/python-certifi/tree/f4bc676bc101fe2235846e37044e8c693d6cbaf4

cacert.pem SHA-256：9cc2a774b5198dcff14d9be1e66091f538975d867ce029a96bce15a55dfd730f

cacert.pem 与 LICENSE 原样取自该提交。构建复制为引擎旁的 core/cacert.pem 和
core/CA-LICENSE。更新版本时需同步替换证书、许可证、出处和文件摘要。
