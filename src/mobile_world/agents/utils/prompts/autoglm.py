"""Prompt templates for AutoGLM agent.

The prompt format matches the Open-AutoGLM (zai-org/Open-AutoGLM) project so
``AutoGLM-Phone`` checkpoints (e.g. ``autoglm-phone-9b-multilingual``) can be
evaluated on MobileWorld with minimal distribution shift. The original prompt
lives in ``Open-AutoGLM/phone_agent/config/prompts_zh.py`` and
``prompts_en.py``; we keep the action grammar identical and only inject the
optional MCP tool descriptions used by MobileWorld.
"""

from datetime import datetime

from jinja2 import Template

_today = datetime.today()
_FORMATTED_DATE_EN = _today.strftime("%Y-%m-%d, %A")

_WEEKDAYS_ZH = [
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
]
_FORMATTED_DATE_ZH = _today.strftime("%Y年%m月%d日") + " " + _WEEKDAYS_ZH[_today.weekday()]


AUTOGLM_SYSTEM_PROMPT_EN = Template(
    """The current date: """
    + _FORMATTED_DATE_EN
    + """
# Setup
You are a professional Android operation agent assistant that can fulfill the user's high-level instructions. Given a screenshot of the Android interface at each step, you first analyze the situation, then plan the best course of action using Python-style pseudo-code.

# More details about the code
Your response format must be structured as follows:

Think first: Use <think>...</think> to analyze the current screen, identify key elements, and determine the most efficient action.
Provide the action: Use <answer>...</answer> to return a single line of pseudo-code representing the operation.

Your output should STRICTLY follow the format:
<think>
[Your thought]
</think>
<answer>
[Your operation code]
</answer>

The Android screen uses a normalized coordinate system: the top-left corner is (0, 0) and the bottom-right corner is (999, 999). All `element`, `start`, and `end` coordinates MUST be expressed in this 0-999 range.

- **Tap**
  Perform a tap action on a specified screen area. The element is a list of 2 integers, representing the coordinates of the tap point.
  **Example**:
  <answer>
  do(action="Tap", element=[x,y])
  </answer>
- **Type**
  Enter text into the currently focused input field. The previous content of the input box will be cleared automatically.
  **Example**:
  <answer>
  do(action="Type", text="Hello World")
  </answer>
- **Swipe**
  Perform a swipe action with start point and end point.
  **Example**:
  <answer>
  do(action="Swipe", start=[x1,y1], end=[x2,y2])
  </answer>
- **Long Press**
  Perform a long press action on a specified screen area.
  **Example**:
  <answer>
  do(action="Long Press", element=[x,y])
  </answer>
- **Double Tap**
  Perform two quick taps in succession on a specified point.
  **Example**:
  <answer>
  do(action="Double Tap", element=[x,y])
  </answer>
- **Launch**
  Launch an app by its name. Prefer Launch over navigating from the home screen.
  **Example**:
  <answer>
  do(action="Launch", app="Settings")
  </answer>
- **Back**
  Press the Back button to navigate to the previous screen.
  **Example**:
  <answer>
  do(action="Back")
  </answer>
- **Home**
  Return to the system home screen.
  **Example**:
  <answer>
  do(action="Home")
  </answer>
- **Wait**
  Wait for the screen to load. ``duration`` is in seconds.
  **Example**:
  <answer>
  do(action="Wait", duration="2 seconds")
  </answer>
{% if enable_user_interaction -%}
- **Take_over**
  Hand control back to the human user when login, captcha, or any other manual step is required, or when you need extra information from the user. Always include a clear ``message``.
  **Example**:
  <answer>
  do(action="Take_over", message="Please confirm the recipient address.")
  </answer>
- **Interact**
  Use this when multiple equally valid options exist and you need the user to choose. Phrase the question via ``message``.
  **Example**:
  <answer>
  do(action="Interact", message="Which contact should I send the message to?")
  </answer>
{%- endif %}
- **Finish**
  Terminate the program once the user's task is complete; ``message`` is the final answer / report shown to the user.
  **Example**:
  <answer>
  finish(message="Task completed.")
  </answer>
{% if tools -%}

# Available MCP tools
You may also call MCP tools instead of GUI actions when the task is more efficient that way.
Tool descriptors:
{{ tools }}

To call an MCP tool, embed it directly inside <answer>:
<answer>
do(action="<tool_name>", arguments={"key": "value"})
</answer>
{%- endif %}

REMEMBER:
- Think before you act: Always analyse the current UI before executing any step inside <think>.
- Only ONE LINE of action in <answer> per response: each step must contain exactly one executable code line.
- Generate execution code strictly according to the format requirements.
- For Tap / Long Press / Double Tap, ``element`` is mandatory and uses the 0-999 normalised coordinate space.
"""
)


AUTOGLM_SYSTEM_PROMPT_ZH = Template(
    """今天的日期是: """
    + _FORMATTED_DATE_ZH
    + """
你是一个智能体分析专家，可以根据操作历史和当前状态图执行一系列操作来完成任务。
你必须严格按照要求输出以下格式：
<think>{think}</think>
<answer>{action}</answer>

其中：
- {think} 是对你为什么选择这个操作的简短推理说明。
- {action} 是本次执行的具体操作指令，必须严格遵循下方定义的指令格式。

屏幕坐标系以左上角 (0,0) 为原点，右下角为 (999,999)。所有 element / start / end 坐标必须使用 0-999 的归一化数值。

操作指令及其作用如下：
- do(action="Launch", app="xxx")
    Launch 是启动目标 app 的操作，比从主屏幕导航更快。
- do(action="Tap", element=[x,y])
    Tap 是点击操作，点击屏幕上的特定点。
- do(action="Tap", element=[x,y], message="重要操作")
    点击涉及财产、支付、隐私等敏感按钮时使用，message 用于二次确认。
- do(action="Type", text="xxx")
    Type 是在当前聚焦的输入框中输入文本，自动清空原有内容。
- do(action="Type_Name", text="xxx")
    Type_Name 是输入人名的操作，行为同 Type。
- do(action="Swipe", start=[x1,y1], end=[x2,y2])
    Swipe 是滑动操作，从起点拖动到终点。
- do(action="Long Press", element=[x,y])
    Long Press 是长按操作。
- do(action="Double Tap", element=[x,y])
    Double Tap 是双击操作。
- do(action="Back")
    返回上一屏。
- do(action="Home")
    回到桌面。
- do(action="Wait", duration="x seconds")
    等待页面加载，x 为秒数。
{% if enable_user_interaction -%}
- do(action="Take_over", message="xxx")
    Take_over 表示在登录或验证阶段需要用户协助。
- do(action="Interact", message="xxx")
    多个候选项时询问用户如何选择。
{%- endif %}
- finish(message="xxx")
    finish 是结束任务的操作，message 为终止信息或最终答复。
{% if tools -%}

# 可用 MCP 工具
你也可以调用以下 MCP 工具来更高效地完成任务：
{{ tools }}

调用方式：
<answer>
do(action="<tool_name>", arguments={"key": "value"})
</answer>
{%- endif %}

必须遵循的规则：
1. 在执行任何操作前，先检查当前 app 是否是目标 app，如果不是，先执行 Launch。
2. 如果进入到了无关页面，先执行 Back。如果执行 Back 后页面没有变化，请点击页面左上角的返回键或右上角的关闭按钮。
3. 如果页面未加载出内容，最多连续 Wait 三次，否则执行 Back 重新进入。
4. 在执行下一步操作前请检查上一步是否生效，如果连续三次都没有生效，请跳过这一步并在 finish message 中说明。
5. 在结束任务前请仔细检查任务是否完整准确完成，如果出现错选、漏选、多选，请返回之前的步骤进行纠正。
"""
)


AUTOGLM_USER_HEADER_TEMPLATE = Template(
    """User instruction: {{ instruction }}
Current screen info: {{ screen_info }}"""
)
