import json
from typing import Dict, List, Any

__all__ = ["PRICE_DECISION_PROMPT", "PAYMENT_METHOD_PROMPT"]

# 产品价格决策prompt
PRICE_DECISION_PROMPT = """As a dynamic price decision-making system for an intelligent enterprise agent, please determine an optimal and proactive product price based on the following information:

Company Information:
- Business name: {company_name}

Product Information:
- Product name: {product_name}
- Total production cost: {total_cost}, Raw material expenses: {material_cost}
- Current market selling price for similar products: {market_price}

Business Status:
- Current available funds: {current_fund}
- Current inventory: {current_stock}
- Recent sales performance: {base_price}

Pricing Guidelines:
1. The price must always cover costs (especially considering raw material expense fluctuations) and ensure a sustainable profit margin.
2. The price should react dynamically to market selling price changes, staying competitive while protecting company profitability.
3. The price should adjust proactively based on inventory levels and recent sales performance to optimize turnover.
4. The price should align with the company`s financial capacity and production ability, prioritizing long-term growth and stability.
5. If both total cost and raw material expenses are 0 or -1, it indicates the product is being produced for the first time, and the pricing decision should be made with extra caution to ensure market acceptance and long-term profitability.
6. It is essential to note that the final pricing must still refer to the base_price and should not exceed it by a large margin; cannot exceed 1.5 times the base price. The base_price:{base_price}

Please return the result in JSON format with the following fields:
- price: The proposed selling price of the product
- reasoning: A short explanation (no more than 100 words) showing how cost trends, raw material expenses, and market prices influenced the decision.

Example return format:
{{
"price": 50,
"reasoning": "Due to recent increases in raw material costs and higher market prices, the product price is adjusted above the previous base to secure margins while remaining competitive."
}}
"""



# 付款方式决策prompt
PAYMENT_METHOD_PROMPT = """As a payment method decision-making system for an intelligent enterprise agent, decide on the appropriate payment method based on the following information:

company information:
- The name of the business: {company_name}

Business Status:
- Current funding: {current_fund}
- Current inventory: {current_stock}
- Sell Price: {sell_price}
- Liquidity: {fund_liquidity}

Transaction Information:
- Deal Type: {transaction_type} # "Purchase"(Purchase of someone else's product) or "Sale"(Sell your own products)
- Transaction amount: {transaction_amount}
- Trading Partner: {transaction_partner}

Please use the above information to determine the most suitable payment method. Consider the following factors:
1. The company's current funding position and liquidity
2. Inventory and sales volume
3. The size of the transaction amount
4. Historical relationship with the counterparty

For installments, specify the number of installments and interest; For one-time payments, specify the payment time.

Please return the result in JSON format with the following fields:
- payment_method: "installment" or "full_payment" (one-time payment)
- details: Payment details, which vary depending on the payment method
    - In the case of installments, "installment_count" (installments) and "interest_rate" (annual interest rate)
    - In the case of a one-time payment, include "payment_days" (how many days after delivery)
- reasoning: Reasons for the decision (no more than 100 words)

Example return format (installments):
{{
    "payment_method": "installment",
    "details": {{
        "installment_count": 3,
        "interest_rate": 0.05
    }},
    "reasoning": "Due to the large transaction amount and limited current funds, choose 3 instalments to reduce the financial pressure while offering a reasonable interest rate to maintain a good relationship."
}}

Example return format (one-time payment):
{{
    "payment_method": "full_payment",
    "details": {{
        "payment_days": 30
    }},
    "reasoning": "The business is well-funded, opting for a one-time payment within 30 days of delivery in order to simplify the transaction process and get a possible cash discount."
}}
"""