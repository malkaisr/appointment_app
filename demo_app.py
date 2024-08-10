from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

proxy_client = TwilioHttpClient(proxy={'http': 'http://proxy-chain.intel.com:916', 'https': 'http://proxy-chain.intel.com:916'})
account_sid = 'AC6687331bb2d392bf3b3cee82d1d61e8e'
auth_token = '8339b8615c62c3f817b3790aa6b42626'
client = Client(account_sid, auth_token, http_client=proxy_client)

message = client.messages.create(
    body="Your appointment is confirmed.",
    from_='+12294945742',
    to='+9720525990335'
)

print(message.sid)