# D-Eye in plain language

**What it is.** D-Eye gives an AI assistant a safe, honest way to look things up
on the web and hand you back answers *with their sources attached* - every claim
traceable to a page, with a timestamp and a fingerprint so you can check it later.

**Why it's careful.** By default it only *reads*. It will not log in as you, click
buttons, buy things, or touch private/internal addresses on your network. Anything
that changes something has to be switched on deliberately.

**Getting started (three lines).**
1. `deye setup` - prepares a private folder on your computer.
2. `deye doctor` - checks everything is healthy.
3. `deye research "your question"` - produces a tidy, cited report file.

**Using it inside Claude.** You register D-Eye once for the way you use Claude:
- On your computer (Claude Desktop / Code): one settings entry.
- On the website (Chat / Projects): one "custom connector".
Then Claude can use D-Eye's search and research tools when you ask it to.

**The honest bit.** There is no magic single button that turns it on everywhere
at once - the website and your computer are separate worlds for good security
reasons. `deye doctor --surfaces` always tells you, in plain terms, where D-Eye
is switched on and what (if anything) is left to do.
