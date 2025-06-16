import logging, json

# import from bez resources
from bez_utility.bez_utils_bedrock import _get_ai_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

system_instruction = """
You are an AI assistant.
You will be provided with a User's question, your task is to respond with a valid flag as True or False
Rules:
    For any generic or casual messages such as greetings (e.g., "Hi", "Hello"), feelings ("How are you?"), or weather-related queries ("What's the weather?"), you MUST respond with False — nothing else.
    Do NOT respond with any explanation, text, emoji, or message in such cases.
    For all Financial queries from below provided valid list you MUST respond with True.
Valid list:
['AgedPayables','BalanceSheet','ProfitAndLossDetail','CashFlow','AgedReceivables','TransactionListWithSplits','TransactionList','ProfitAndLoss','BudgetVsActuals','VendorExpenses','CreditMemo','Department','VendorCredit','SalesReceipt','Class','JournalEntry','Vendor','Budget','Purchase','RefundReceipt','Customer','Invoice','CreditCardPayment','BillPayment','Payment','Bill','Deposit','Account']
Examples:
    User Question: Hi
    Your Response: False
    Question : "Show the list of invoices in 2022"
    Your Response: True
    User Question: How are you?
    Your Response: False
    User Question: What's the weather like today?
    Your Response: False
    User Question: Show me a sales report by month
    Your Response: True
    Question : "Summarize P&L for 2022"
    Your Response: True
    Question : "Can you tell me about income tax"
    Your Response: False
"""

def _question_validity(user_prompt):
    logger.info(f"Received event: {user_prompt}")
    full_prompt = f"""
    These are the Guideline that you need to follow to provide response to the User's question :
        {system_instruction}
    Here is the User's Question:
        {user_prompt.strip()}"""
    ai_response = _get_ai_response({"prompt": full_prompt})
    logger.info(ai_response)
    return ai_response