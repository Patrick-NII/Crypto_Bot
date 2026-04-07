"""Structured error catalog for trading exceptions.

Centralizes all Binance error codes and CCXT exception types with:
- user-friendly French messages
- category (balance, permission, validation, rate_limit, network, market)
- severity (info, warning, error)
- retry strategy (none, immediate, exponential_backoff)

Exposed to frontend via GET /orders/error-catalog.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

import ccxt

ErrorCategory = Literal["balance", "permission", "validation", "rate_limit", "network", "market", "unknown"]
ErrorSeverity = Literal["info", "warning", "error"]
RetryStrategy = Literal["none", "immediate", "exponential_backoff"]


@dataclass
class ErrorDetail:
    code: str
    category: ErrorCategory
    severity: ErrorSeverity
    user_message: str
    retry_strategy: RetryStrategy = "none"
    technical_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Binance error codes → ErrorDetail ──
# Reference: https://binance-docs.github.io/apidocs/spot/en/#error-codes
_BINANCE_CATALOG: dict[int, ErrorDetail] = {
    # ── Validation / parameters ──
    -1013: ErrorDetail(
        "BINANCE_-1013", "validation", "error",
        "Montant trop petit. Minimum requis par Binance (~5 USDT).",
    ),
    -1021: ErrorDetail(
        "BINANCE_-1021", "network", "warning",
        "Desynchronisation avec Binance. Reessayez dans un instant.",
        retry_strategy="immediate",
    ),
    -1100: ErrorDetail(
        "BINANCE_-1100", "validation", "error",
        "Requete invalide. Verifiez les parametres de l'ordre.",
    ),
    -1102: ErrorDetail(
        "BINANCE_-1102", "validation", "error",
        "Parametre obligatoire manquant.",
    ),
    -1106: ErrorDetail(
        "BINANCE_-1106", "validation", "error",
        "Parametre envoye inutilement.",
    ),
    -1111: ErrorDetail(
        "BINANCE_-1111", "validation", "error",
        "Precision du montant incorrecte.",
    ),
    -1121: ErrorDetail(
        "BINANCE_-1121", "market", "error",
        "Symbole invalide ou inconnu sur Binance.",
    ),
    -1125: ErrorDetail(
        "BINANCE_-1125", "market", "warning",
        "ListenKey invalide ou expire.",
    ),
    -1130: ErrorDetail(
        "BINANCE_-1130", "validation", "error",
        "Parametre invalide dans la requete.",
    ),

    # ── Rate limits & server ──
    -1003: ErrorDetail(
        "BINANCE_-1003", "rate_limit", "warning",
        "Trop de requetes. Attendez quelques secondes.",
        retry_strategy="exponential_backoff",
    ),
    -1006: ErrorDetail(
        "BINANCE_-1006", "network", "warning",
        "Erreur inattendue de Binance. Reessayez.",
        retry_strategy="exponential_backoff",
    ),
    -1007: ErrorDetail(
        "BINANCE_-1007", "network", "warning",
        "Binance n'a pas repondu a temps. Reessayez.",
        retry_strategy="exponential_backoff",
    ),
    -1008: ErrorDetail(
        "BINANCE_-1008", "network", "error",
        "Maintenance Binance en cours. Reessayez plus tard.",
        retry_strategy="exponential_backoff",
    ),
    -1015: ErrorDetail(
        "BINANCE_-1015", "rate_limit", "warning",
        "Limite d'ordres atteinte. Ralentissez la frequence.",
        retry_strategy="exponential_backoff",
    ),
    -1016: ErrorDetail(
        "BINANCE_-1016", "network", "error",
        "Service Binance temporairement indisponible (maintenance).",
        retry_strategy="exponential_backoff",
    ),

    # ── Authentication / permissions ──
    -1022: ErrorDetail(
        "BINANCE_-1022", "permission", "error",
        "Signature invalide. Verifiez vos cles API dans Settings.",
    ),
    -2014: ErrorDetail(
        "BINANCE_-2014", "permission", "error",
        "Format de cle API invalide.",
    ),
    -2015: ErrorDetail(
        "BINANCE_-2015", "permission", "error",
        "Cle API invalide, IP non autorisee ou permissions manquantes.",
    ),

    # ── Balance / trading ──
    -2010: ErrorDetail(
        "BINANCE_-2010", "balance", "error",
        "Solde insuffisant ou paire non autorisee pour ce compte.",
    ),
    -2011: ErrorDetail(
        "BINANCE_-2011", "validation", "warning",
        "Annulation de l'ordre rejetee.",
    ),
    -2013: ErrorDetail(
        "BINANCE_-2013", "market", "warning",
        "Ordre introuvable (deja execute ou annule).",
    ),
    -2018: ErrorDetail(
        "BINANCE_-2018", "balance", "error",
        "Solde insuffisant pour cette action.",
    ),
    -2019: ErrorDetail(
        "BINANCE_-2019", "balance", "error",
        "Marge insuffisante.",
    ),

    # ── Spot-specific order errors ──
    -4001: ErrorDetail(
        "BINANCE_-4001", "validation", "error",
        "Quantite hors des limites autorisees.",
    ),
    -4007: ErrorDetail(
        "BINANCE_-4007", "permission", "warning",
        "Compte en mode maker-only. Les ordres market sont bloques.",
    ),
    -4010: ErrorDetail(
        "BINANCE_-4010", "validation", "error",
        "Quantite invalide (precision non respectee).",
    ),
    -4014: ErrorDetail(
        "BINANCE_-4014", "balance", "error",
        "Solde insuffisant pour cette action.",
    ),
    -4024: ErrorDetail(
        "BINANCE_-4024", "validation", "warning",
        "Ordre declencherait immediatement - annule.",
    ),
    -4025: ErrorDetail(
        "BINANCE_-4025", "validation", "warning",
        "Ordre reduce-only rejete : aucune position ouverte.",
    ),
    -4028: ErrorDetail(
        "BINANCE_-4028", "validation", "error",
        "Quantite trop petite pour la precision de cette paire.",
    ),
    -4051: ErrorDetail(
        "BINANCE_-4051", "validation", "error",
        "Quantite invalide (doit etre positive apres les frais).",
    ),
    -4052: ErrorDetail(
        "BINANCE_-4052", "validation", "warning",
        "Ordre IOC/FOK rejete (conditions non remplies).",
    ),

    # ── Market status ──
    -3000: ErrorDetail(
        "BINANCE_-3000", "market", "error",
        "Erreur interne du marche. Reessayez.",
        retry_strategy="exponential_backoff",
    ),
    -3020: ErrorDetail(
        "BINANCE_-3020", "balance", "error",
        "Transfert rejete : compte source incorrect.",
    ),
}


# ── CCXT exception types → ErrorDetail ──
_CCXT_CATALOG: dict[type, ErrorDetail] = {}


def _init_ccxt_catalog() -> None:
    _CCXT_CATALOG.update({
        ccxt.InsufficientFunds: ErrorDetail(
            "CCXT_InsufficientFunds", "balance", "error",
            "Solde insuffisant pour cet ordre.",
        ),
        ccxt.InvalidOrder: ErrorDetail(
            "CCXT_InvalidOrder", "validation", "error",
            "Ordre invalide. Verifiez le montant et la paire.",
        ),
        ccxt.OrderNotFound: ErrorDetail(
            "CCXT_OrderNotFound", "validation", "warning",
            "Ordre introuvable (deja execute, annule ou expire).",
        ),
        ccxt.AuthenticationError: ErrorDetail(
            "CCXT_AuthenticationError", "permission", "error",
            "Cle API invalide ou permissions manquantes. Verifiez Settings.",
        ),
        ccxt.PermissionDenied: ErrorDetail(
            "CCXT_PermissionDenied", "permission", "error",
            "Permission refusee. Votre cle API n'autorise pas cette action.",
        ),
        ccxt.InvalidNonce: ErrorDetail(
            "CCXT_InvalidNonce", "network", "warning",
            "Horloge desynchronisee. Reessayez.",
            retry_strategy="immediate",
        ),
        ccxt.RateLimitExceeded: ErrorDetail(
            "CCXT_RateLimitExceeded", "rate_limit", "warning",
            "Trop de requetes. Attendez quelques secondes.",
            retry_strategy="exponential_backoff",
        ),
        ccxt.DDoSProtection: ErrorDetail(
            "CCXT_DDoSProtection", "rate_limit", "warning",
            "Protection anti-DDoS Binance activee. Attendez.",
            retry_strategy="exponential_backoff",
        ),
        ccxt.ExchangeNotAvailable: ErrorDetail(
            "CCXT_ExchangeNotAvailable", "network", "error",
            "Binance temporairement indisponible. Reessayez plus tard.",
            retry_strategy="exponential_backoff",
        ),
        ccxt.NetworkError: ErrorDetail(
            "CCXT_NetworkError", "network", "warning",
            "Erreur reseau. Verifiez votre connexion.",
            retry_strategy="exponential_backoff",
        ),
        ccxt.RequestTimeout: ErrorDetail(
            "CCXT_RequestTimeout", "network", "warning",
            "Binance n'a pas repondu a temps. Reessayez.",
            retry_strategy="exponential_backoff",
        ),
        ccxt.BadRequest: ErrorDetail(
            "CCXT_BadRequest", "validation", "error",
            "Requete incorrecte. Verifiez les parametres.",
        ),
        ccxt.NotSupported: ErrorDetail(
            "CCXT_NotSupported", "market", "error",
            "Operation non supportee par Binance.",
        ),
        ccxt.BadSymbol: ErrorDetail(
            "CCXT_BadSymbol", "market", "error",
            "Symbole invalide ou inconnu sur Binance.",
        ),
        ccxt.ExchangeError: ErrorDetail(
            "CCXT_ExchangeError", "unknown", "error",
            "Erreur Binance. Reessayez dans un instant.",
        ),
    })


_init_ccxt_catalog()


# ── Custom app error codes (not from Binance) ──
APP_ERRORS: dict[str, ErrorDetail] = {
    "APP_MIN_NOTIONAL_SELL": ErrorDetail(
        "APP_MIN_NOTIONAL_SELL", "market", "error",
        "Valeur de vente trop faible pour atteindre le minimum Binance.",
    ),
    "APP_NO_QUOTE_BALANCE": ErrorDetail(
        "APP_NO_QUOTE_BALANCE", "balance", "error",
        "Aucun solde dans la devise de cotation. Convertissez d'abord.",
    ),
    "APP_NO_BASE_BALANCE": ErrorDetail(
        "APP_NO_BASE_BALANCE", "balance", "error",
        "Aucun solde de l'actif a vendre.",
    ),
    "APP_PAIR_NOT_FOUND": ErrorDetail(
        "APP_PAIR_NOT_FOUND", "market", "error",
        "Paire non disponible sur Binance pour votre compte.",
    ),
    "APP_CONVERSION_NEEDED": ErrorDetail(
        "APP_CONVERSION_NEEDED", "balance", "warning",
        "Conversion necessaire avant cet achat.",
    ),
    "APP_HIGH_SLIPPAGE": ErrorDetail(
        "APP_HIGH_SLIPPAGE", "market", "warning",
        "Slippage eleve attendu (ordre > 0.5% du volume 24h).",
    ),
    "APP_WALLET_LOCKED": ErrorDetail(
        "APP_WALLET_LOCKED", "permission", "error",
        "Wallet verrouille. Debloquez l'acces dans Settings.",
    ),
    "APP_LIVE_TRADING_DISABLED": ErrorDetail(
        "APP_LIVE_TRADING_DISABLED", "permission", "error",
        "Trading live desactive sur votre connexion Binance.",
    ),
    "APP_UNKNOWN": ErrorDetail(
        "APP_UNKNOWN", "unknown", "error",
        "Erreur inattendue. Reessayez.",
    ),
}


def classify_error(exc: Exception) -> ErrorDetail:
    """Parse any exception and return a structured ErrorDetail.

    Order of precedence:
    1. Binance error code extracted from exception message
    2. CCXT exception type mapping
    3. Generic fallback with truncated message
    """
    msg = str(exc)

    # 1. Binance error code in message
    code_match = re.search(r'"code"\s*:\s*(-?\d+)', msg)
    if code_match:
        code = int(code_match.group(1))
        if code in _BINANCE_CATALOG:
            detail = _BINANCE_CATALOG[code]
            return ErrorDetail(
                code=detail.code,
                category=detail.category,
                severity=detail.severity,
                user_message=detail.user_message,
                retry_strategy=detail.retry_strategy,
                technical_message=msg[:200],
            )

    # 2. CCXT exception type (check subclasses first — most specific)
    for exc_type, detail in _CCXT_CATALOG.items():
        if isinstance(exc, exc_type):
            return ErrorDetail(
                code=detail.code,
                category=detail.category,
                severity=detail.severity,
                user_message=detail.user_message,
                retry_strategy=detail.retry_strategy,
                technical_message=msg[:200],
            )

    # 3. ValueError from our own code (usually preflight-driven)
    if isinstance(exc, ValueError) and len(msg) <= 250 and "{" not in msg:
        return ErrorDetail(
            code="APP_VALIDATION",
            category="validation",
            severity="error",
            user_message=msg,
            retry_strategy="none",
            technical_message=msg[:200],
        )

    # 4. Fallback
    return ErrorDetail(
        code="APP_UNKNOWN",
        category="unknown",
        severity="error",
        user_message="Erreur lors de l'execution. Reessayez.",
        retry_strategy="none",
        technical_message=msg[:200],
    )


def get_full_catalog() -> list[dict[str, Any]]:
    """Return the full error catalog as a list (for API endpoint)."""
    entries: list[dict[str, Any]] = []

    for detail in _BINANCE_CATALOG.values():
        entries.append(detail.to_dict())

    for detail in _CCXT_CATALOG.values():
        entries.append(detail.to_dict())

    for detail in APP_ERRORS.values():
        entries.append(detail.to_dict())

    return entries


def get_app_error(key: str) -> ErrorDetail:
    """Return an app-level error by key, with fallback."""
    return APP_ERRORS.get(key, APP_ERRORS["APP_UNKNOWN"])
