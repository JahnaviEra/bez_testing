import markdown, io
from xhtml2pdf import pisa
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _convert_to_pdf(msg_data):
    # Build HTML content
    html_content = """
    <html>
        <head>
            <style>
                body {
            font-family: 'Arial', sans-serif;
            background-color: #f7f7f7;
            padding: 20px;
                }
                .message-container {
                    margin-bottom: 20px;
                    max-width: 70%;
                    padding: 10px;
                    border-radius: 15px;
                    position: relative;
                }
                .user {
                    background-color: #d1e8ff;
                    margin-left: auto;
                    text-align: left;
                }
                .bez {
                    background-color: #f1f0f0;
                    margin-right: auto;
                    text-align: left;
                }
                .sender-name {
                    font-weight: bold;
                    font-size: 12px;
                    margin-bottom: 5px;
                    color: #333;
                }
                .timestamp {
                    font-size: 10px;
                    color: #777;
                    text-align: right;
                    margin-top: 5px;
                }
                .chat-content {
                    font-size: 13px;
                    color: #111;
                    margin-top: 5px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }
                th, td {
                    border: 1px solid #999;
                    padding: 8px;
                    text-align: center;
                }
                th {
                    background-color: #e2e2e2;
                }
            </style>
        </head>
        <body>
    """
    for msg in msg_data:
        for component in msg:
            # logger.info(component)
            if component == 'created_at':
                continue
            if "User " in component:
                sender = component.replace("User ", "")
                message = msg[f"{component}"]
                msg_type = 'User'
                timestamp = msg.get('created_at', '')
            elif "Agent " in component:
                sender = component.replace("Agent ", "")
                message = msg[f"{component}"]
                msg_type = 'Bez'
                # logger.info(f"{sender} {message}")
                timestamp = msg.get('created_at', '')

            # Convert Markdown message to HTML
            message_html = markdown.markdown(message)
            logger.info(message_html)

            bubble_class = 'user' if sender == 'User' else 'bez'

            html_content += f"""
            <div class="message-container {bubble_class}">
                <div class="sender-name">{sender}</div>
                {message_html}
                <div class="timestamp">{timestamp}</div>
            </div>
            """
    # Base64 encode for binary file response
    # Generate PDF
    pdf_buffer = io.BytesIO()
    pisa.CreatePDF(html_content, dest=pdf_buffer)
    pdf_buffer.seek(0)
    logger.info(pdf_buffer)
    return pdf_buffer