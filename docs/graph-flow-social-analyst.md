# Graph flow: Social Media Analyst (social-only run)

## Flow

1. **No tool results yet** → Node returns a synthetic `AIMessage` with `tool_calls` for `get_ticker_quote` and `get_reddit_company_social` (search_terms = [ticker]). Graph runs tools → back to Social Analyst.

2. **After first tool round** (2 ToolMessages: quote + Reddit) → Node invokes the LLM with `bind_tools([get_reddit_company_social])`. The LLM may:
   - **Call the tool again** with different `search_terms` (e.g. company name from quote, sector) if results were insufficient → graph runs the tool again, then loops back (max one retry).
   - **Return no tool_calls** → node gets structured report from the conversation and returns it.

3. **After second tool round** (3+ ToolMessages) or when LLM did not retry → Node runs prompt + `with_structured_output(SocialMediaAnalysisOutput)` and returns the report. Graph goes to Msg Clear → next analyst.

## Graph structure (social only)

```
START → Social Analyst → (synthetic tool_calls) → tools_social → extract_resources → Social Analyst
                                                                        ↓
                                    [LLM may retry Reddit with new search_terms → tools_social → …]
                                                                        ↓
                                 (report, no tool_calls) → Msg Clear → Bull Researcher → ...
```
