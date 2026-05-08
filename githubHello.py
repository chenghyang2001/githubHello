from datetime import datetime, timezone, timedelta

def div(a, b):
    return a / b

print("Hello from githubHello!")

taiwan_tz = timezone(timedelta(hours=8))
current_time = datetime.now(taiwan_tz)
formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
print(f"Current date and time: {formatted_time} (GMT+8)")

result = div(4, 2)
print(f"Result: 4 / 2 = {result}")
