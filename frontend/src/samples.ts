export const sampleAlerts = [
  {
    label: "SSH brute force",
    value: `Failed login detected
User: admin
Source IP: 185.199.111.45
Attempts: 47
Time: 02:13 AM
Country: Unknown
Service: SSH`,
  },
  {
    label: "Phishing email",
    value: `Phishing alert
Sender: security-update@payroll-example.com
Recipient: maria@company.com
Subject: Urgent password verification required
URL: https://payroll-example-login.xyz/session
Attachment: benefits_update.html`,
  },
  {
    label: "Endpoint malware",
    value: `Endpoint malware detected
Host: FIN-LAPTOP-22
User: finance.user
Process: invoice_viewer.exe
Hash: 44d88612fea8a8f36de82e1278abb02f
Detection: Trojan quarantined`,
  },
  {
    label: "Suspicious login",
    value: `Successful login from unusual country
User: alex@company.com
Source IP: 91.240.118.12
Country: Unknown
Time: 03:48 AM
MFA: not satisfied
Device: new browser`,
  },
  {
    label: "Web SQL injection",
    value: `Web attack alert
Source IP: 203.0.113.77
Host: ecommerce-web-01
URL: /products?id=12 UNION SELECT username,password FROM users
Status: HTTP 500
Detection: SQL injection payload`,
  },
];
