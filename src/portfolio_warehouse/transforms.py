from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from portfolio_warehouse.db import connect
from portfolio_warehouse.ibkr_csv import parse_date, parse_datetime, parse_decimal


def _get(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_hash(report_type: str, payload: Mapping[str, Any]) -> str:
    normalized = {
        key: str(value).strip()
        for key, value in sorted(payload.items())
        if value is not None and str(value).strip() != ""
    }
    raw = json.dumps({"report_type": report_type, "payload": normalized}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _decimal_sum(*values: Any) -> Decimal | None:
    parsed = [value for value in (parse_decimal(item) for item in values) if value is not None]
    if not parsed:
        return None
    return sum(parsed, Decimal("0"))


def rebuild_staging() -> None:
    with connect() as conn:
        with conn.transaction():
            conn.execute(
                """
                truncate
                    staging.ibkr_trade,
                    staging.ibkr_cash_transaction,
                    staging.ibkr_interest,
                    staging.ibkr_corporate_action,
                    staging.ibkr_nav_snapshot,
                    staging.ibkr_mark_to_market_performance,
                    staging.ibkr_symbol_performance,
                    staging.ibkr_asset_class_change,
                    staging.ibkr_account_period_performance,
                    staging.ibkr_key_statistics,
                    staging.ibkr_position_snapshot
                """
            )
            _load_flex_statement_rows(conn)


def _load_flex_statement_rows(conn: Any) -> None:
    rows = conn.execute(
        """
        select r.report_id, r.account_id, r.section_code, r.row_number, r.raw_payload
        from raw.ibkr_flex_statement_row r
        join raw.report_file f on f.report_id = r.report_id
        order by f.ingested_at, r.report_id, r.row_number
        """
    ).fetchall()
    cnav_rows: list[tuple[str, Mapping[str, Any]]] = []

    for row in rows:
        payload = row["raw_payload"]
        section_code = row["section_code"]
        if section_code == "TRNT":
            _insert_trade(conn, row["report_id"], payload)
        elif section_code == "CTRN":
            _insert_cash(conn, row["report_id"], payload)
        elif section_code == "TIER":
            _insert_interest(conn, row["report_id"], payload)
        elif section_code == "CORP":
            _insert_corporate_action(conn, row["report_id"], payload)
        elif section_code == "POST":
            _insert_flex_position_snapshot(conn, row["report_id"], payload)
        elif section_code == "EQUT":
            _insert_nav_snapshot(conn, row["report_id"], payload)
            _insert_flex_cash_snapshot(conn, row["report_id"], payload)
            _insert_flex_accrual_snapshot(conn, row["report_id"], payload)
        elif section_code == "CNAV":
            _insert_flex_account_performance(conn, row["report_id"], payload)
            cnav_rows.append((row["report_id"], payload))
        elif section_code == "MTMP":
            _insert_mark_to_market_performance(conn, row["report_id"], payload)
        elif section_code == "MYTD":
            _insert_symbol_performance(conn, row["report_id"], payload)
        elif section_code == "CPOV":
            _insert_asset_class_change(conn, row["report_id"], payload)

    _insert_flex_key_statistics(conn, cnav_rows)


def _insert_trade(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    transaction_id = _clean_text(payload.get("TransactionID"))
    if not transaction_id:
        return
    trade_dt = parse_datetime(payload.get("DateTime"))
    conn.execute(
        """
        insert into staging.ibkr_trade (
            report_id, transaction_id, trade_id, account_id, trade_datetime, trade_date,
            settle_date, symbol, description, isin, asset_class, buy_sell, quantity,
            trade_price, trade_money, proceeds, taxes, ib_commission, net_cash,
            cost_basis, fifo_pnl_realized, mtm_pnl, currency, exchange, order_type
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (transaction_id) do update set
            report_id = excluded.report_id,
            trade_id = excluded.trade_id,
            account_id = excluded.account_id,
            trade_datetime = excluded.trade_datetime,
            trade_date = excluded.trade_date,
            settle_date = excluded.settle_date,
            symbol = excluded.symbol,
            description = excluded.description,
            isin = excluded.isin,
            asset_class = excluded.asset_class,
            buy_sell = excluded.buy_sell,
            quantity = excluded.quantity,
            trade_price = excluded.trade_price,
            trade_money = excluded.trade_money,
            proceeds = excluded.proceeds,
            taxes = excluded.taxes,
            ib_commission = excluded.ib_commission,
            net_cash = excluded.net_cash,
            cost_basis = excluded.cost_basis,
            fifo_pnl_realized = excluded.fifo_pnl_realized,
            mtm_pnl = excluded.mtm_pnl,
            currency = excluded.currency,
            exchange = excluded.exchange,
            order_type = excluded.order_type
        """,
        (
            report_id,
            transaction_id,
            _clean_text(payload.get("TradeID")),
            _clean_text(payload.get("ClientAccountID")),
            trade_dt,
            parse_date(payload.get("TradeDate")),
            parse_date(payload.get("SettleDateTarget")),
            _clean_text(payload.get("Symbol")),
            _clean_text(payload.get("Description")),
            _clean_text(payload.get("ISIN")),
            _clean_text(payload.get("AssetClass")),
            _clean_text(payload.get("Buy/Sell")),
            parse_decimal(payload.get("Quantity")),
            parse_decimal(payload.get("TradePrice")),
            parse_decimal(payload.get("TradeMoney")),
            parse_decimal(payload.get("Proceeds")),
            parse_decimal(payload.get("Taxes")),
            parse_decimal(payload.get("IBCommission")),
            parse_decimal(payload.get("NetCash")),
            parse_decimal(payload.get("CostBasis")),
            parse_decimal(payload.get("FifoPnlRealized")),
            parse_decimal(payload.get("MtmPnl")),
            _clean_text(payload.get("CurrencyPrimary")),
            _clean_text(payload.get("Exchange")),
            _clean_text(payload.get("OrderType")),
        ),
    )


def _insert_cash(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    transaction_id = _clean_text(payload.get("TransactionID"))
    if not transaction_id:
        return
    cash_dt = parse_datetime(payload.get("Date/Time"))
    conn.execute(
        """
        insert into staging.ibkr_cash_transaction (
            report_id, transaction_id, account_id, cash_datetime, cash_date, settle_date,
            currency, amount, type, description, symbol, isin, trade_id, client_reference
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (transaction_id) do update set
            report_id = excluded.report_id,
            account_id = excluded.account_id,
            cash_datetime = excluded.cash_datetime,
            cash_date = excluded.cash_date,
            settle_date = excluded.settle_date,
            currency = excluded.currency,
            amount = excluded.amount,
            type = excluded.type,
            description = excluded.description,
            symbol = excluded.symbol,
            isin = excluded.isin,
            trade_id = excluded.trade_id,
            client_reference = excluded.client_reference
        """,
        (
            report_id,
            transaction_id,
            _clean_text(payload.get("ClientAccountID")),
            cash_dt,
            cash_dt.date() if cash_dt else None,
            parse_date(payload.get("SettleDate")),
            _clean_text(payload.get("CurrencyPrimary")),
            parse_decimal(payload.get("Amount")),
            _clean_text(payload.get("Type")),
            _clean_text(payload.get("Description")),
            _clean_text(payload.get("Symbol")),
            _clean_text(payload.get("ISIN")),
            _clean_text(payload.get("TradeID")),
            _clean_text(payload.get("ClientReference")),
        ),
    )


def _insert_interest(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    if not _clean_text(payload.get("ClientAccountID")):
        return
    source_row_hash = _row_hash("tier_interest", payload)
    conn.execute(
        """
        insert into staging.ibkr_interest (
            report_id, source_row_hash, account_id, report_date, value_date, currency, interest_type,
            total_principal, rate, total_interest, code
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (source_row_hash) do update set
            report_id = excluded.report_id,
            account_id = excluded.account_id,
            report_date = excluded.report_date,
            value_date = excluded.value_date,
            currency = excluded.currency,
            interest_type = excluded.interest_type,
            total_principal = excluded.total_principal,
            rate = excluded.rate,
            total_interest = excluded.total_interest,
            code = excluded.code
        """,
        (
            report_id,
            source_row_hash,
            _clean_text(payload.get("ClientAccountID")),
            parse_date(payload.get("ReportDate")),
            parse_date(payload.get("ValueDate")),
            _clean_text(payload.get("CurrencyPrimary")),
            _clean_text(payload.get("InterestType")),
            parse_decimal(payload.get("TotalPrincipal")),
            parse_decimal(payload.get("Rate")),
            parse_decimal(payload.get("TotalInterest")),
            _clean_text(payload.get("Code")),
        ),
    )


def _insert_corporate_action(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    transaction_id = _clean_text(payload.get("TransactionID"))
    if not transaction_id and not _clean_text(payload.get("ActionDescription")):
        return
    corporate_action_id = transaction_id or _row_hash("corporate_actions", payload)
    action_dt = parse_datetime(payload.get("Date/Time"))
    conn.execute(
        """
        insert into staging.ibkr_corporate_action (
            report_id, corporate_action_id, transaction_id, account_id, report_date, action_datetime, symbol,
            isin, action_description, amount, proceeds, value, quantity, cost_basis, type
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (corporate_action_id) do update set
            report_id = excluded.report_id,
            transaction_id = excluded.transaction_id,
            account_id = excluded.account_id,
            report_date = excluded.report_date,
            action_datetime = excluded.action_datetime,
            symbol = excluded.symbol,
            isin = excluded.isin,
            action_description = excluded.action_description,
            amount = excluded.amount,
            proceeds = excluded.proceeds,
            value = excluded.value,
            quantity = excluded.quantity,
            cost_basis = excluded.cost_basis,
            type = excluded.type
        """,
        (
            report_id,
            corporate_action_id,
            transaction_id,
            _clean_text(payload.get("ClientAccountID")),
            parse_date(_get(payload, "Report Date", "ReportDate")),
            action_dt,
            _clean_text(payload.get("Symbol")),
            _clean_text(payload.get("ISIN")),
            _clean_text(payload.get("ActionDescription")),
            parse_decimal(payload.get("Amount")),
            parse_decimal(payload.get("Proceeds")),
            parse_decimal(payload.get("Value")),
            parse_decimal(payload.get("Quantity")),
            parse_decimal(payload.get("CostBasis")),
            _clean_text(payload.get("Type")),
        ),
    )


def _insert_nav_snapshot(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    account_id = _clean_text(payload.get("ClientAccountID"))
    as_of = parse_date(payload.get("ReportDate"))
    if not account_id or not as_of:
        return
    conn.execute(
        """
        insert into staging.ibkr_nav_snapshot (
            report_id, account_id, as_of_date, currency, cash, stock, options, bonds, funds,
            dividend_accruals, interest_accruals, fee_accruals, total
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (account_id, as_of_date) do update set
            report_id = excluded.report_id,
            currency = excluded.currency,
            cash = excluded.cash,
            stock = excluded.stock,
            options = excluded.options,
            bonds = excluded.bonds,
            funds = excluded.funds,
            dividend_accruals = excluded.dividend_accruals,
            interest_accruals = excluded.interest_accruals,
            fee_accruals = excluded.fee_accruals,
            total = excluded.total
        """,
        (
            report_id,
            account_id,
            as_of,
            _clean_text(payload.get("CurrencyPrimary")),
            parse_decimal(payload.get("Cash")),
            parse_decimal(payload.get("Stock")),
            parse_decimal(payload.get("Options")),
            parse_decimal(payload.get("Bonds")),
            parse_decimal(payload.get("Funds")),
            parse_decimal(payload.get("DividendAccruals")),
            parse_decimal(payload.get("InterestAccruals")),
            parse_decimal(payload.get("BrokerFeesAccrualsComponent")),
            parse_decimal(payload.get("Total")),
        ),
    )


def _insert_mark_to_market_performance(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    account_id = _clean_text(payload.get("ClientAccountID"))
    report_date = parse_date(payload.get("ReportDate"))
    symbol = _clean_text(payload.get("Symbol"))
    description = _clean_text(payload.get("Description"))
    if not account_id or not report_date or (not symbol and not description):
        return
    source_row_hash = _row_hash(
        "mark_to_market_performance",
        {
            "account_id": account_id,
            "report_date": report_date,
            "asset_class": _clean_text(payload.get("AssetClass")),
            "symbol": symbol,
            "description": description,
            "isin": _clean_text(payload.get("ISIN")),
        },
    )
    conn.execute(
        """
        insert into staging.ibkr_mark_to_market_performance (
            source_row_hash, report_id, account_id, report_date, asset_class, sub_category, symbol,
            description, isin, previous_close_quantity, previous_close_price, close_quantity, close_price,
            transaction_mtm_pnl, prior_open_mtm_pnl, commissions, other, total, total_with_accruals
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (source_row_hash) do update set
            report_id = excluded.report_id,
            account_id = excluded.account_id,
            report_date = excluded.report_date,
            asset_class = excluded.asset_class,
            sub_category = excluded.sub_category,
            symbol = excluded.symbol,
            description = excluded.description,
            isin = excluded.isin,
            previous_close_quantity = excluded.previous_close_quantity,
            previous_close_price = excluded.previous_close_price,
            close_quantity = excluded.close_quantity,
            close_price = excluded.close_price,
            transaction_mtm_pnl = excluded.transaction_mtm_pnl,
            prior_open_mtm_pnl = excluded.prior_open_mtm_pnl,
            commissions = excluded.commissions,
            other = excluded.other,
            total = excluded.total,
            total_with_accruals = excluded.total_with_accruals
        """,
        (
            source_row_hash,
            report_id,
            account_id,
            report_date,
            _clean_text(payload.get("AssetClass")),
            _clean_text(payload.get("SubCategory")),
            symbol,
            description,
            _clean_text(payload.get("ISIN")),
            parse_decimal(payload.get("PreviousCloseQuantity")),
            parse_decimal(payload.get("PrevClosePrice")),
            parse_decimal(payload.get("CloseQuantity")),
            parse_decimal(payload.get("ClosePrice")),
            parse_decimal(payload.get("TransactionMtmPnl")),
            parse_decimal(payload.get("PriorOpenMtmPnl")),
            parse_decimal(payload.get("Commissions")),
            parse_decimal(payload.get("Other")),
            parse_decimal(payload.get("Total")),
            parse_decimal(payload.get("TotalWithAccruals")),
        ),
    )


def _insert_symbol_performance(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    account_id = _clean_text(payload.get("ClientAccountID"))
    symbol = _clean_text(payload.get("Symbol"))
    description = _clean_text(payload.get("Description"))
    if not account_id or (not symbol and not description):
        return
    source_row_hash = _row_hash(
        "symbol_performance",
        {
            "account_id": account_id,
            "asset_class": _clean_text(payload.get("AssetClass")),
            "symbol": symbol,
            "description": description,
            "isin": _clean_text(payload.get("ISIN")),
        },
    )
    conn.execute(
        """
        insert into staging.ibkr_symbol_performance (
            source_row_hash, report_id, account_id, asset_class, sub_category, symbol,
            description, isin, mtm_mtd, mtm_ytd, realized_pnl_mtd, realized_pnl_ytd
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (source_row_hash) do update set
            report_id = excluded.report_id,
            account_id = excluded.account_id,
            asset_class = excluded.asset_class,
            sub_category = excluded.sub_category,
            symbol = excluded.symbol,
            description = excluded.description,
            isin = excluded.isin,
            mtm_mtd = excluded.mtm_mtd,
            mtm_ytd = excluded.mtm_ytd,
            realized_pnl_mtd = excluded.realized_pnl_mtd,
            realized_pnl_ytd = excluded.realized_pnl_ytd
        """,
        (
            source_row_hash,
            report_id,
            account_id,
            _clean_text(payload.get("AssetClass")),
            _clean_text(payload.get("SubCategory")),
            symbol,
            description,
            _clean_text(payload.get("ISIN")),
            parse_decimal(payload.get("Mark-to-Market MTD")),
            parse_decimal(payload.get("Mark-to-Market YTD")),
            parse_decimal(payload.get("RealizedPnlMTD")),
            parse_decimal(payload.get("RealizedPnlYTD")),
        ),
    )


def _insert_asset_class_change(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    account_id = _clean_text(payload.get("ClientAccountID"))
    asset_class = _clean_text(payload.get("AssetClass"))
    if not account_id or not asset_class:
        return
    source_row_hash = _row_hash(
        "asset_class_change",
        {"account_id": account_id, "asset_class": asset_class, "currency": _clean_text(payload.get("CurrencyPrimary"))},
    )
    conn.execute(
        """
        insert into staging.ibkr_asset_class_change (
            source_row_hash, report_id, account_id, currency, asset_class, prior_period_value,
            transactions, mtm_pnl_prior_period_positions, mtm_pnl_transactions, corporate_actions,
            other, account_transfers, linking_adjustments, fx_translation_pnl,
            future_price_adjustments, settled_cash, end_of_period_value
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (source_row_hash) do update set
            report_id = excluded.report_id,
            account_id = excluded.account_id,
            currency = excluded.currency,
            asset_class = excluded.asset_class,
            prior_period_value = excluded.prior_period_value,
            transactions = excluded.transactions,
            mtm_pnl_prior_period_positions = excluded.mtm_pnl_prior_period_positions,
            mtm_pnl_transactions = excluded.mtm_pnl_transactions,
            corporate_actions = excluded.corporate_actions,
            other = excluded.other,
            account_transfers = excluded.account_transfers,
            linking_adjustments = excluded.linking_adjustments,
            fx_translation_pnl = excluded.fx_translation_pnl,
            future_price_adjustments = excluded.future_price_adjustments,
            settled_cash = excluded.settled_cash,
            end_of_period_value = excluded.end_of_period_value
        """,
        (
            source_row_hash,
            report_id,
            account_id,
            _clean_text(payload.get("CurrencyPrimary")),
            asset_class,
            parse_decimal(payload.get("Prior Period Value")),
            parse_decimal(payload.get("Transactions")),
            parse_decimal(payload.get("MtmPnlPriorPeriodPositions")),
            parse_decimal(payload.get("MtmPnlTransactions")),
            parse_decimal(payload.get("CorporateActions")),
            parse_decimal(payload.get("Other")),
            parse_decimal(payload.get("AccountTransfers")),
            parse_decimal(payload.get("LinkingAdjustments")),
            parse_decimal(payload.get("FXTranslationPnl")),
            parse_decimal(payload.get("FuturePriceAdjustments")),
            parse_decimal(payload.get("SettledCash")),
            parse_decimal(payload.get("EndOfPeriodValue")),
        ),
    )


def _insert_flex_account_performance(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    account_id = _clean_text(payload.get("ClientAccountID"))
    period_start = parse_date(payload.get("FromDate"))
    period_end = parse_date(payload.get("ToDate"))
    if not account_id or not period_start or not period_end:
        return
    conn.execute(
        """
        insert into staging.ibkr_account_period_performance (
            report_id, account_id, name, period_start, period_end, beginning_nav,
            ending_nav, period_return, deposits, withdrawals, dividends, interest, fees
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (account_id, period_start, period_end) do update set
            report_id = excluded.report_id,
            name = excluded.name,
            beginning_nav = excluded.beginning_nav,
            ending_nav = excluded.ending_nav,
            period_return = excluded.period_return,
            deposits = excluded.deposits,
            withdrawals = excluded.withdrawals,
            dividends = excluded.dividends,
            interest = excluded.interest,
            fees = excluded.fees
        """,
        (
            report_id,
            account_id,
            _clean_text(payload.get("AccountAlias")),
            period_start,
            period_end,
            parse_decimal(payload.get("StartingValue")),
            parse_decimal(payload.get("EndingValue")),
            parse_decimal(payload.get("TWR")),
            parse_decimal(payload.get("DepositsWithdrawals")),
            None,
            _decimal_sum(payload.get("Dividends"), payload.get("ChangeInDividendAccruals")),
            _decimal_sum(payload.get("Interest"), payload.get("ChangeInInterestAccruals")),
            _decimal_sum(
                payload.get("BrokerFees"),
                payload.get("changeInBrokerFeeAccruals"),
                payload.get("AdvisorFees"),
                payload.get("ClientFees"),
                payload.get("OtherFees"),
                payload.get("Commissions"),
                payload.get("ForexCommissions"),
                payload.get("TransactionTax"),
                payload.get("SalesTax"),
            ),
        ),
    )


def _insert_flex_key_statistics(conn: Any, rows: list[tuple[str, Mapping[str, Any]]]) -> None:
    grouped: dict[tuple[str, date, date], list[Mapping[str, Any]]] = {}
    for report_id, payload in rows:
        period_start = parse_date(payload.get("FromDate"))
        period_end = parse_date(payload.get("ToDate"))
        if period_start and period_end:
            grouped.setdefault((report_id, period_start, period_end), []).append(payload)

    for (report_id, period_start, period_end), payloads in grouped.items():
        beginning_nav = _sum_payloads(payloads, "StartingValue")
        ending_nav = _sum_payloads(payloads, "EndingValue")
        mtm = _sum_payloads(payloads, "Mtm")
        deposits_withdrawals = _sum_payloads(payloads, "DepositsWithdrawals")
        period_return = _weighted_return(payloads)
        dividends = _sum_payloads(payloads, "Dividends", "ChangeInDividendAccruals")
        interest = _sum_payloads(payloads, "Interest", "ChangeInInterestAccruals")
        fees_commissions = _sum_payloads(
            payloads,
            "BrokerFees",
            "changeInBrokerFeeAccruals",
            "AdvisorFees",
            "ClientFees",
            "OtherFees",
            "Commissions",
            "ForexCommissions",
            "TransactionTax",
            "SalesTax",
        )
        other = _sum_payloads(payloads, "Other", "OtherIncome", "FxTranslation", "LinkingAdjustments")
        change_in_nav = None
        if beginning_nav is not None and ending_nav is not None:
            change_in_nav = ending_nav - beginning_nav

        conn.execute(
            """
            insert into staging.ibkr_key_statistics (
                report_id, period_start, period_end, beginning_nav, ending_nav, period_return,
                one_month_return, three_month_return, mtm, deposits_withdrawals, dividends,
                interest, fees_commissions, other, change_in_nav
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (period_start, period_end) do update set
                report_id = excluded.report_id,
                beginning_nav = excluded.beginning_nav,
                ending_nav = excluded.ending_nav,
                period_return = excluded.period_return,
                one_month_return = excluded.one_month_return,
                three_month_return = excluded.three_month_return,
                mtm = excluded.mtm,
                deposits_withdrawals = excluded.deposits_withdrawals,
                dividends = excluded.dividends,
                interest = excluded.interest,
                fees_commissions = excluded.fees_commissions,
                other = excluded.other,
                change_in_nav = excluded.change_in_nav
            """,
            (
                report_id,
                period_start,
                period_end,
                beginning_nav,
                ending_nav,
                period_return,
                None,
                None,
                mtm,
                deposits_withdrawals,
                dividends,
                interest,
                fees_commissions,
                other,
                change_in_nav,
            ),
        )


def _sum_payloads(payloads: list[Mapping[str, Any]], *keys: str) -> Decimal | None:
    values: list[Decimal] = []
    for payload in payloads:
        for key in keys:
            value = parse_decimal(payload.get(key))
            if value is not None:
                values.append(value)
    if not values:
        return None
    return sum(values, Decimal("0"))


def _weighted_return(payloads: list[Mapping[str, Any]]) -> Decimal | None:
    weighted_values: list[Decimal] = []
    total_weight = Decimal("0")
    fallback_values: list[Decimal] = []
    for payload in payloads:
        twr = parse_decimal(payload.get("TWR"))
        if twr is None:
            continue
        fallback_values.append(twr)
        ending_nav = parse_decimal(payload.get("EndingValue"))
        if ending_nav is not None and ending_nav > 0:
            weighted_values.append(twr * ending_nav)
            total_weight += ending_nav
    if weighted_values and total_weight > 0:
        return sum(weighted_values, Decimal("0")) / total_weight
    if fallback_values:
        return sum(fallback_values, Decimal("0")) / Decimal(len(fallback_values))
    return None


def _insert_flex_position_snapshot(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    account_id = _clean_text(payload.get("ClientAccountID"))
    symbol = _clean_text(payload.get("Symbol"))
    description = _clean_text(payload.get("Description"))
    as_of = parse_date(payload.get("ReportDate"))
    if not account_id or not as_of or (not symbol and not description):
        return
    position_snapshot_id = _row_hash(
        "flex_position_snapshot_key",
        {
            "account_id": account_id,
            "as_of_date": as_of,
            "symbol": symbol,
            "description": description,
            "isin": _clean_text(payload.get("ISIN")),
            "asset_class": _clean_text(payload.get("AssetClass")),
        },
    )
    _upsert_position_snapshot(
        conn,
        position_snapshot_id=position_snapshot_id,
        report_id=report_id,
        account_id=account_id,
        as_of_date=as_of,
        financial_instrument=_clean_text(payload.get("AssetClass")),
        currency=_clean_text(payload.get("CurrencyPrimary")),
        symbol=symbol,
        description=description,
        sector=_clean_text(payload.get("SubCategory")),
        quantity=parse_decimal(payload.get("Quantity")),
        close_price=parse_decimal(payload.get("MarkPrice")),
        market_value=parse_decimal(payload.get("PositionValue")),
        cost_basis=parse_decimal(payload.get("CostBasisMoney")),
        unrealized_pnl=parse_decimal(payload.get("FifoPnlUnrealized")),
        fx_rate_to_base=parse_decimal(payload.get("FXRateToBase")),
        is_total=False,
    )


def _insert_flex_cash_snapshot(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    account_id = _clean_text(payload.get("ClientAccountID"))
    as_of = parse_date(payload.get("ReportDate"))
    cash = parse_decimal(payload.get("Cash"))
    if not account_id or not as_of or cash is None:
        return
    position_snapshot_id = _row_hash(
        "flex_cash_snapshot_key",
        {"account_id": account_id, "as_of_date": as_of, "currency": _clean_text(payload.get("CurrencyPrimary"))},
    )
    _upsert_position_snapshot(
        conn,
        position_snapshot_id=position_snapshot_id,
        report_id=report_id,
        account_id=account_id,
        as_of_date=as_of,
        financial_instrument="Cash",
        currency=_clean_text(payload.get("CurrencyPrimary")),
        symbol="CASH",
        description="Cash",
        sector=None,
        quantity=None,
        close_price=None,
        market_value=cash,
        cost_basis=None,
        unrealized_pnl=None,
        fx_rate_to_base=None,
        is_total=False,
    )


def _insert_flex_accrual_snapshot(conn: Any, report_id: str, payload: Mapping[str, Any]) -> None:
    account_id = _clean_text(payload.get("ClientAccountID"))
    as_of = parse_date(payload.get("ReportDate"))
    accruals = _decimal_sum(
        payload.get("DividendAccruals"),
        payload.get("LiteSurchargeAccruals"),
        payload.get("CGTWithholdingAccruals"),
        payload.get("InterestAccruals"),
        payload.get("IncentiveCouponAccruals"),
        payload.get("BrokerFeesAccrualsComponent"),
    )
    if not account_id or not as_of or accruals is None or accruals == 0:
        return
    position_snapshot_id = _row_hash(
        "flex_accrual_snapshot_key",
        {"account_id": account_id, "as_of_date": as_of, "currency": _clean_text(payload.get("CurrencyPrimary"))},
    )
    _upsert_position_snapshot(
        conn,
        position_snapshot_id=position_snapshot_id,
        report_id=report_id,
        account_id=account_id,
        as_of_date=as_of,
        financial_instrument="Accruals",
        currency=_clean_text(payload.get("CurrencyPrimary")),
        symbol="ACCRUALS",
        description="Accruals",
        sector=None,
        quantity=None,
        close_price=None,
        market_value=accruals,
        cost_basis=None,
        unrealized_pnl=None,
        fx_rate_to_base=None,
        is_total=False,
    )


def _upsert_position_snapshot(
    conn: Any,
    *,
    position_snapshot_id: str,
    report_id: str,
    account_id: str | None,
    as_of_date: date | None,
    financial_instrument: str | None,
    currency: str | None,
    symbol: str | None,
    description: str | None,
    sector: str | None,
    quantity: Decimal | None,
    close_price: Decimal | None,
    market_value: Decimal | None,
    cost_basis: Decimal | None,
    unrealized_pnl: Decimal | None,
    fx_rate_to_base: Decimal | None,
    is_total: bool,
) -> None:
    conn.execute(
        """
        insert into staging.ibkr_position_snapshot (
            position_snapshot_id, report_id, account_id, as_of_date, financial_instrument, currency, symbol,
            description, sector, quantity, close_price, market_value, cost_basis, unrealized_pnl,
            fx_rate_to_base, is_total
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (position_snapshot_id) do update set
            report_id = excluded.report_id,
            account_id = excluded.account_id,
            as_of_date = excluded.as_of_date,
            financial_instrument = excluded.financial_instrument,
            currency = excluded.currency,
            symbol = excluded.symbol,
            description = excluded.description,
            sector = excluded.sector,
            quantity = excluded.quantity,
            close_price = excluded.close_price,
            market_value = excluded.market_value,
            cost_basis = excluded.cost_basis,
            unrealized_pnl = excluded.unrealized_pnl,
            fx_rate_to_base = excluded.fx_rate_to_base,
            is_total = excluded.is_total
        """,
        (
            position_snapshot_id,
            report_id,
            account_id,
            as_of_date,
            financial_instrument,
            currency,
            symbol,
            description,
            sector,
            quantity,
            close_price,
            market_value,
            cost_basis,
            unrealized_pnl,
            fx_rate_to_base,
            is_total,
        ),
    )
