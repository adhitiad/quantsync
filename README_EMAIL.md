# Panduan Konfigurasi DNS untuk Postal Server

Agar email memiliki reputasi tinggi dan tidak dianggap spam, tambahkan record berikut di Dashboard DNS Anda:

### 1. SPF (Sender Policy Framework)
Memberi tahu dunia server mana yang diizinkan mengirim email atas nama domain Anda.
*   **Type**: TXT
*   **Host**: `@`
*   **Value**: `v=spf1 ip4:IP_SERVER_ANDA include:spf.postal.io ~all`

### 2. DKIM (DomainKeys Identified Mail)
Tanda tangan digital untuk memverifikasi bahwa email tidak diubah selama transmisi.
*   **Type**: TXT
*   **Host**: `postal._domainkey`
*   **Value**: (Ambil nilai Public Key dari dashboard admin Postal setelah setup domain)

### 3. DMARC (Domain-based Message Authentication)
Kebijakan jika SPF atau DKIM gagal.
*   **Type**: TXT
*   **Host**: `_dmarc`
*   **Value**: `v=DMARC1; p=quarantine; adkim=s; aspf=s;`

### 4. Reverse DNS (PTR Record)
Sangat penting! Minta provider VPS Anda untuk mensetting PTR record IP Server Anda ke hostname server (misal: `mail.quantsync.com`).
