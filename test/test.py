import os
from zai import ZhipuAiClient

client = ZhipuAiClient(api_key=os.environ["ZHIPU_API_KEY"])
response = client.chat.completions.create(
    model="glm-4.6v",  
    messages=[
        {
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://cloudcovert-1305175928.cos.ap-guangzhou.myqcloud.com/%E5%9B%BE%E7%89%87grounding.PNG"
                    }
                },
                {
                    "type": "text",
                    "text": "桌子上从右边数第二瓶啤酒在哪里？请以 [[xmin, ymin, xmax, ymax]] 格式提供坐标。"
                }
            ],
            "role": "user"
        }
    ],
    thinking={
        "type":"enabled"
    },
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.reasoning_content:
        print(chunk.choices[0].delta.reasoning_content, end='', flush=True)

    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end='', flush=True)