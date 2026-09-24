<a id="top"></a>

<div align="center">

  <h1>Telex Security Policy</h1>
  <p><b>Vulnerability Disclosure, Cryptographic Hygiene & Self-Hosting Best Practices</b></p>

  <p>
    <img src="https://img.shields.io/badge/Security-Fernet%20Encryption-14B8A6?style=flat-square" alt="Fernet Encryption" />
    <img src="https://img.shields.io/badge/Webhooks-HMAC--SHA256-050508?style=flat-square" alt="HMAC-SHA256" />
    <img src="https://img.shields.io/badge/Automerge-Disabled%20by%20Design-F43F5E?style=flat-square" alt="Zero Automerge" />
  </p>

  <br>

  <p>
    <a href="#supported-versions"><b>Supported Versions</b></a> &nbsp;•&nbsp;
    <a href="#reporting-a-vulnerability"><b>Reporting</b></a> &nbsp;•&nbsp;
    <a href="#what-to-expect"><b>Expectations</b></a> &nbsp;•&nbsp;
    <a href="#self-hosting-practices"><b>Self-Hosting Practices</b></a>
  </p>

</div>

<br>

---

<br>

## <a id="supported-versions"></a>01. Supported Versions

We actively maintain and provide security updates for the following releases of Telex:

| Version | Supported Status | Security Notice |
|---|---|---|
| **0.1.x** | :white_check_mark: Supported | Active branch receiving regular dependency and patch updates |
| **< 0.1.0** | :x: Unsupported | Deprecated preview builds; please upgrade to current main |

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="reporting-a-vulnerability"></a>02. Reporting a Vulnerability

We prioritize the security of Telex, our users' source code, and connected repository credentials.

If you discover a potential vulnerability in Telex, **please do not open a public GitHub issue or discussion.**

Instead, please submit your findings through GitHub's **Private Vulnerability Reporting**:

1. Navigate to the [Telex Security Advisories](https://github.com/Kesavaraja67/telex/security/advisories) tab.
2. Click **"Report a vulnerability"**.
3. Provide a detailed disclosure, including:
   - Category of vulnerability (e.g. authentication bypass, secret exposure, code injection, privilege escalation).
   - Step-by-step reproduction steps or a minimal proof of concept (PoC).
   - Potential impact and affected modules (`apps/api`, `apps/web`, or CI/CD pipelines).

Alternatively, you may contact maintainers directly via email:  
**krkesavaraja67@gmail.com**

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="what-to-expect"></a>03. What to Expect

- **Initial Response**: We will acknowledge receipt of your vulnerability report within **24 hours**.
- **Triage & Assessment**: We will confirm the vulnerability and provide an estimated timeline for remediation within **72 hours**.
- **Coordination**: We will coordinate with you to test and verify the fix prior to public disclosure.
- **Credit**: We will credit your discovery in our Security Advisories release notes (unless you prefer to remain anonymous).

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="self-hosting-practices"></a>04. Self-Hosting Security Practices

1. **Production Secret Management**: Never commit private keys (`GITHUB_APP_PRIVATE_KEY`), webhook secrets, or session secrets to source control. Always inject credentials via environment variables or a dedicated KMS / Secrets Manager.
2. **BYOK Encryption**: Generate a cryptographically secure Fernet key via `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and supply it as `TELEX_ENCRYPTION_KEY`.
3. **Database Security**: Ensure the production PostgreSQL database user is restricted to minimal necessary table permissions.
4. **CORS Restrictions**: Explicitly configure `CORS_ORIGINS` to trusted domains. Never permit wildcards (`*`) when credentials are enabled.

<br>

<div align="center">
  <a href="#top">
    <img src="https://img.shields.io/badge/%E2%86%91-Back%20to%20Top-050508?style=flat-square&logoColor=white" alt="Back to Top" />
  </a>
</div>
