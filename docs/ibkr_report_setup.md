# IBKR Report Setup

This warehouse expects IBKR CSV attachments. Configure IBKR first, then wire iCloud IMAP to download those attachments into `data/inbox`.

## Source Reports

Create saved Activity Flex Queries for the recurring event feeds:

- `Trades`
- `Cash`
- `Interest`
- `Corporate_Actions`

Keep the output format as `CSV`. Include both accounts (`U24765593`, `U25245520`) in the query account selector.

For PortfolioAnalyst summary snapshots, keep using the PortfolioAnalyst report export for now. IBKR documents automatic delivery for statements and Flex Queries clearly; PortfolioAnalyst scheduling needs to be confirmed in the actual Client Portal UI.

## Create Activity Flex Queries

In Client Portal:

1. Go to `Performance & Reports > Flex Queries`.
2. In `Activity Flex Query`, click `+`.
3. Name the query after the file the pipeline expects, for example `Trades`.
4. Select the relevant section and fields.
5. In `Delivery Configuration`:
   - Accounts: select both IBKR accounts.
   - Format: `CSV`.
   - Period: use `Last N Calendar Days` with `7` for daily email delivery, or `Last Business Day` if you want smaller files.
6. Continue, review, and create the query.

Using a rolling 7-day period is more resilient to weekends, holidays, late booking, and missed local runs. The warehouse keeps immutable raw files and deduplicates staging rows by IBKR transaction IDs where available.

## Enable Email Delivery

After creating the saved Flex Queries:

1. Go to `Performance & Reports > Flex Queries`.
2. In `Flex Queries Delivery`, click the gear icon.
3. Configure the delivery method.
4. Choose `Email` unless you have separately requested sFTP from IBKR.
5. Tick each saved Activity Flex Query that should be delivered.
6. Continue and confirm.

## Recommended Cadence

Start with:

- Daily: `Trades`, `Cash`, `Interest`, `Corporate_Actions`
- Weekly or monthly: PortfolioAnalyst summary CSV

Once the email workflow is stable, consider moving Flex Query retrieval from email to IBKR Flex Web Service. Flex Web Service lets software request pre-configured Flex Queries over HTTPS without logging into Client Portal, which is cleaner than scraping email attachments.

## References

- Create Activity Flex Queries: https://www.ibkrguides.com/clientportal/performanceandstatements/activityflex.htm
- Configure Flex Query delivery: https://www.ibkrguides.com/clientportal/performanceandstatements/deliverysettingsflex.htm
- Run statements and saved reports: https://www.ibkrguides.com/clientportal/performanceandstatements/runstatement.htm
- Enable Flex Web Service: https://www.ibkrguides.com/clientportal/performanceandstatements/flex-web-service.htm
- IBKR Campus Reporting Tools overview: https://www.interactivebrokers.com/campus/trading-lessons/client-portal-reporting/

