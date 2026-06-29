from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from portfolio_warehouse.db import connect
from portfolio_warehouse.ibkr_csv import parse_date, parse_datetime, parse_decimal, parse_period


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
                    staging.ibkr_account_period_performance,
                    staging.ibkr_key_statistics,
                    staging.ibkr_position_snapshot,
                    staging.ibkr_benchmark_return
                """
            )
            _load_flex_rows(conn)
            _load_flex_statement_rows(conn)
            _load_portfolio_summary_rows(conn)


def _load_flex_rows(conn: Any) -> None:
    rows = conn.execute(
        """
        select r.report_id, r.report_type, r.row_number, r.raw_payload
        from raw.ibkr_flex_row r
        join raw.report_file f on f.report_id = r.report_id
        order by f.ingested_at, r.report_id, r.row_number
        """
    ).fetchall()
    for row in rows:
        payload = row["raw_payload"]
        report_type = row["report_type"]
        if report_type == "flex_trades":
            _insert_trade(conn, row["report_id"], payload)
        elif report_type == "flex_cash":
            _insert_cash(conn, row["report_id"], payload)
        elif report_type == "flex_interest":
            _insert_interest(conn, row["report_id"], payload)
        elif report_type == "flex_corporate_actions":
            _insert_corporate_action(conn, row["report_id"], payload)


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
            _insert_flex_cash_snapshot(conn, row["report_id"], payload)
        elif section_code == "CNAV":
            _insert_flex_account_performance(conn, row["report_id"], payload)
            cnav_rows.append((row["report_id"], payload))

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
    source_row_hash = _row_hash("flex_interest", payload)
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
    corporate_action_id = transaction_id or _row_hash("flex_corporate_actions", payload)
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
                None,
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


def _load_portfolio_summary_rows(conn: Any) -> None:
    rows = conn.execute(
        """
        select r.report_id, r.row_number, r.section, r.row_type, r.raw_values
        from raw.ibkr_portfolio_summary_row r
        join raw.report_file f on f.report_id = r.report_id
        order by f.ingested_at, r.report_id, r.row_number
        """
    ).fetchall()

    headers: dict[tuple[str, str], list[str]] = {}
    current_header: dict[tuple[str, str], list[str]] = {}
    meta: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        report_id = row["report_id"]
        section = row["section"]
        row_type = row["row_type"]
        key = (str(report_id), section)
        values = row["raw_values"].get("values", [])

        if row_type == "MetaInfo" and len(values) >= 2:
            meta.setdefault(key, {})[values[0]] = values[1]
            continue
        if row_type == "Header":
            headers[key] = values
            current_header[key] = values
            continue
        if row_type != "Data":
            continue

        header = current_header.get(key) or headers.get(key)
        if not header:
            continue
        data = {column: values[index] if index < len(values) else "" for index, column in enumerate(header)}
        if section == "Breakdown of Accounts":
            _insert_account_period_performance(conn, report_id, data, meta.get(key, {}))
        elif section == "Key Statistics":
            _insert_key_statistics(conn, report_id, data, meta.get(key, {}))
        elif section == "Open Position Summary":
            _insert_position_snapshot(conn, report_id, data, meta.get(key, {}))
        elif section == "Historical Performance Benchmark Comparison":
            _insert_benchmark_return(conn, report_id, data, header)


def _analysis_period(meta: Mapping[str, Any]) -> tuple[date | None, date | None]:
    value = _clean_text(meta.get("Analysis Period"))
    return parse_period(value) if value else (None, None)


def _insert_account_period_performance(conn: Any, report_id: str, data: Mapping[str, Any], meta: Mapping[str, Any]) -> None:
    account_id = _clean_text(data.get("Account"))
    if not account_id:
        return
    period_start, period_end = _analysis_period(meta)
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
            _clean_text(data.get("Name")),
            period_start,
            period_end,
            parse_decimal(data.get("Beginning NAV")),
            parse_decimal(data.get("Ending NAV")),
            parse_decimal(data.get("Return")),
            parse_decimal(data.get("Deposits")),
            parse_decimal(data.get("Withdrawals")),
            parse_decimal(data.get("Dividends")),
            parse_decimal(data.get("Interest")),
            parse_decimal(data.get("Fees")),
        ),
    )


def _insert_key_statistics(conn: Any, report_id: str, data: Mapping[str, Any], meta: Mapping[str, Any]) -> None:
    period_start, period_end = _analysis_period(meta)
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
            parse_decimal(data.get("BeginningNAV")),
            parse_decimal(data.get("EndingNAV")),
            parse_decimal(data.get("PeriodReturn")),
            parse_decimal(data.get("1MonthReturn")),
            parse_decimal(data.get("3MonthReturn")),
            parse_decimal(data.get("MTM")),
            parse_decimal(data.get("Deposits & Withdrawals")),
            parse_decimal(data.get("Dividends")),
            parse_decimal(data.get("Interest")),
            parse_decimal(data.get("Fees & Commissions")),
            parse_decimal(data.get("Other")),
            parse_decimal(data.get("ChangeInNAV")),
        ),
    )


def _insert_position_snapshot(conn: Any, report_id: str, data: Mapping[str, Any], meta: Mapping[str, Any]) -> None:
    symbol = _clean_text(data.get("Symbol"))
    financial_instrument = _clean_text(data.get("FinancialInstrument"))
    if not symbol and not financial_instrument:
        return
    as_of = parse_date(meta.get("As Of")) or parse_date(data.get("Date"))
    is_total = _clean_text(data.get("Date")) == "Total"
    position_snapshot_id = _row_hash(
        "portfolio_position_snapshot_key",
        {
            "as_of_date": as_of,
            "financial_instrument": financial_instrument,
            "currency": _clean_text(data.get("Currency")),
            "symbol": symbol,
            "description": _clean_text(data.get("Description")),
            "is_total": is_total,
        },
    )
    _upsert_position_snapshot(
        conn,
        position_snapshot_id=position_snapshot_id,
        report_id=report_id,
        account_id=None,
        as_of_date=as_of,
        financial_instrument=financial_instrument,
        currency=_clean_text(data.get("Currency")),
        symbol=symbol,
        description=_clean_text(data.get("Description")),
        sector=_clean_text(data.get("Sector")),
        quantity=parse_decimal(data.get("Quantity")),
        close_price=parse_decimal(data.get("ClosePrice")),
        market_value=parse_decimal(data.get("Value")),
        cost_basis=parse_decimal(data.get("Cost Basis")),
        unrealized_pnl=parse_decimal(data.get("UnrealizedP&L")),
        fx_rate_to_base=parse_decimal(data.get("FXRateToBase")),
        is_total=is_total,
    )


def _insert_benchmark_return(conn: Any, report_id: str, data: Mapping[str, Any], header: list[str]) -> None:
    period_type = None
    period_label = None
    for candidate in ("Month", "Quarter", "Year"):
        if candidate in header:
            period_type = candidate.lower()
            period_label = _clean_text(data.get(candidate))
            break
    if period_type is None and "Account" in header:
        period_type = "summary"
        period_label = _clean_text(data.get("Account"))
    if not period_label:
        return
    conn.execute(
        """
        insert into staging.ibkr_benchmark_return (
            report_id, period_type, period_label, bm1, bm1_return, bm2, bm2_return,
            account, account_return
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (period_type, period_label, account) do update set
            report_id = excluded.report_id,
            bm1 = excluded.bm1,
            bm1_return = excluded.bm1_return,
            bm2 = excluded.bm2,
            bm2_return = excluded.bm2_return,
            account_return = excluded.account_return
        """,
        (
            report_id,
            period_type,
            period_label,
            _clean_text(data.get("BM1")),
            parse_decimal(data.get("BM1Return")),
            _clean_text(data.get("BM2")),
            parse_decimal(data.get("BM2Return")),
            _clean_text(data.get("Account")),
            parse_decimal(_get(data, "AccountReturn", "Since Inception")),
        ),
    )
