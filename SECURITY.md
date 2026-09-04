# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability within HHGR, please send an email to krishsuthar300@gmail.com. All security vulnerabilities will be promptly addressed.

Please do not report security vulnerabilities through public GitHub issues.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |

## Security Best Practices

When deploying HHGR, follow these guidelines:

- Never commit `.env` files or API keys to version control
- Use environment variables for all secrets (NVIDIA API keys, database credentials)
- Enable HTTPS in production deployments
- Restrict network access to Neo4j, Qdrant, and Redis ports
- Use Docker secrets or a vault for sensitive configuration
