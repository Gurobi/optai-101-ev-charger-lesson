# Where would you put Michigan’s next charging ports?

You’re advising a company with up to $1 million to spend on Level 2 or DC fast charging. Aim to maximize return on investment (ROI) with a target payback period of 10 years or less. At the end of the lesson, tell the investment committee what to fund. You can propose a build, run a pilot, or keep the money until you have better evidence.

Use the [start prompt](../README.md#start-with-your-coding-agent) and put the viewer beside the chat. One partner directs the agent. The other checks its work. Switch roles before the stress test. Save short answers in the viewer. If your agent doesn’t reply automatically, tell it the name of the prompt you just saved.

If you’re using a web-connected chatbot, follow the [chat-only worksheet](CHAT_ONLY.md) and hand in your answers as one Markdown file.

## Lesson outline

| Minutes | What to do together |
|---|---|
| 0–12 · Explore | Read the six tables in order. Look for records you could use to forecast demand and gaps that could affect a site choice. Ask the agent to check something you need to know. |
| 12–22 · Forecast | Choose one quantity you need but can’t read straight from the tables. Compare the agent’s estimates by ZIP area and decide whether to use the forecast. |
| 22–35 · Formulate | Choose an objective, decision variables and limits. Have the agent write the equations. Check a small case by hand, then have the agent run the model. You can use an LP, MIP or stochastic model. |
| 35–50 · Test | Review the first plan. Switch roles and pick one input to change. Save what you think will happen before the agent tries it. If the new conditions rule out the original plan, that’s a result you can use. |
| 50–60 · Recommend | One partner proposes an action. The other challenges the assumption it depends on. Give the committee your advice in 90 seconds. |

If you lack the evidence to recommend a build, still make a model. Use a proxy or a small set of stated assumptions, then test one and explain what the result can support.

Write an observation beside any table. The blue button saves it as you advance. Start a note with `@agent` to ask about that table. After the sixth table, **Notes and replies** collects your observations and the agent’s replies. Choose **Start forecasting** to estimate the same quantity for multiple ZIP areas.

## What to hand in

Download one `student-responses.md` per pair from **Recommend → Submit**. The prompts collect your work as you go. Use **Pitch** for the recommendation itself.

For a build, tell the committee where to install which chargers and how many ports to buy. For a pilot or a decision to wait, name the measurement you need, how you’ll get it, and what finding would justify construction. Support your advice with a result from your test. If the run failed or you used a saved plan, identify the source of the evidence and the claim you can make from it.
