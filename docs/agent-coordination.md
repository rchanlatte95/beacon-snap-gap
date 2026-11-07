# Agent coordination through GitHub issues

Status: DRAFT. Ryan and Ketema must both approve this protocol before agents use it.

Two people work on this repo: Ryan and Ketema. Each person uses one or more AI coding agents. The agents cannot see the chats of the other person. GitHub issues on `ketema/beacon-snap-cliff` are the only channel between the agents. This file gives the rules for that channel.

## 1. Identity

Each agent posts through the GitHub account of its human. Thus the GitHub author of a comment does not identify the agent. Start every issue body and every comment with this header:

```
From: <side>-agent/<agent name>   (for example: ryan-agent/claude-code, ketema-agent/planner)
To: <side>-agent | <side>-human | all
Type: question | handoff | decision-request | info | answer
Needs reply: yes | no
```

`<side>` is `ryan` or `ketema`. A comment without this header is from a human.

## 2. Labels

| Label | Meaning |
|---|---|
| `agent-msg` | The issue is an agent thread. Put it on every agent issue. |
| `to:ryan` | The next action is on the Ryan side. |
| `to:ketema` | The next action is on the Ketema side. |
| `needs-human` | A human must make a decision. Agents must not resolve it. |
| `blocked` | Work on the Ryan side or the Ketema side stops until this issue closes. |

When you reply and the next action moves to the other side, move the `to:` label. Only one `to:` label must be on an issue at a time.

## 3. Rules

1. **One topic for each issue.** Do not add a new topic to an open thread. Open a new issue and link it.
2. **Give evidence.** Refer to file paths with a commit SHA or a branch, and to citation IDs from `docs/data-sources.md` (`DS-*`, `FACT-*`, `F-*`). Do not quote a figure without its source ID.
3. **Humans own decisions.** An agent must not accept a change to scope, requirements (`requirements/`), data rules or the stack for its human. Add `needs-human` and stop.
4. **Do not edit the other side's work.** If you find a problem in a branch or a PR of the other side, write it in an issue or a PR review. Do not push to their branch.
5. **The repo is public.** Do not post secrets, tokens, API keys, personal data or data that we cannot redistribute.
6. **Close the loop.** The side that opened the issue closes it when the answer is received. In the last comment, write the result and the commit or PR that applies it.
7. **Keep it short.** Write in ASD-STE100 style. Use lists and tables. Do not paste large files; link to them.

## 4. How an agent checks for messages

GitHub does not send notifications to agents. At the start of each session, and before you finish a task, run:

```
gh issue list --label agent-msg --label to:<your side> --state open
```

Read each issue and reply, or write in your handoff file why you did not reply.

## 5. Issue template

Title: `[<type>] <short subject>`, for example `[question] Which SNAP threshold does SLICE-1 use?`

```
From: ryan-agent/claude-code
To: ketema-agent
Type: question
Needs reply: yes

## Context
<what you are doing, with file paths and IDs>

## Request
<the exact question or handoff>

## Done when
<the answer or artifact that closes this issue>
```
