# IBKR Report Setup

The MVP source is one saved Activity Flex Query retrieved through IBKR Flex Web Service.

## Flex Query

Create one Activity Flex Query in Client Portal:

1. Go to `Performance & Reports > Flex Queries`.
2. In `Activity Flex Query`, click `+`.
3. Select both accounts: `U24765593` and `U25245520`.
4. Set output format to `CSV`.
5. Use sectioned output with `BOF`, `BOA`, `BOS`, `HEADER`, `DATA`, `EOS`, `EOA`, and `EOF` rows.
6. Use a YTD or full-history period. The warehouse dedupes raw files by SHA-256 and rebuilds staging with business-key upserts.

Include these sections:

- `EQUT`: Net Asset Value (NAV) in Base
- `CNAV`: Change in NAV
- `POST`: Positions
- `TRNT`: Trades
- `CTRN`: Cash Transactions
- `CORP`: Corporate Actions
- `TIER`: Tier Interest Details
- `IACC`: Interest Accruals, optional raw audit support

## Flex Web Service

Enable Flex Web Service and put the credentials in `.env`:

```text
PIPELINE_FETCH_SOURCE=flex
IBKR_FLEX_TOKEN=your_flex_web_service_token
IBKR_FLEX_QUERY_ID=your_saved_flex_query_id
```

Test the request path:

```bash
python scripts/fetch_flex_statement.py --dry-run
```

Download, ingest, rebuild, and validate:

```bash
make fetch-flex
make ingest-local
make rebuild-staging
make validate
```

## References

- Create Activity Flex Queries: https://www.ibkrguides.com/clientportal/performanceandstatements/activityflex.htm
- Configure Flex Query delivery: https://www.ibkrguides.com/clientportal/performanceandstatements/deliverysettingsflex.htm
- Enable Flex Web Service: https://www.ibkrguides.com/clientportal/performanceandstatements/flex-web-service.htm
- Flex Web Service API: https://www.interactivebrokers.com/campus/ibkr-api-page/flex-web-service/
