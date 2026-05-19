# Flight Ticket Tracker

An application that tracks the flight prices from time to time and notifies user while prices are lower. <br>
There are three ends (Desktop, Web and Mobile) for users.

## How It Works

<a href="https://viewer.diagrams.net/?target=blank&highlight=0000ff&edit=_blank&layers=1&nav=1#Uhttps://github.com/CY-Marowak/FlightTicketProject/raw/refs/heads/master/diagram/System%20Architecture.svg">
  <img src="diagram/System%20Architecture.svg" alt="System Architecture" width="100%">
</a>

<br>

<a href="https://viewer.diagrams.net/?lightbox=1&ui=dark&?target=blank&highlight=0000ff&edit=_blank&layers=1&nav=1#Uhttps://github.com/CY-Marowak/FlightTicketProject/raw/refs/heads/master/diagram/Bussiness%20Logic%20flow.svg">
  <img src="diagram/Bussiness%20Logic%20flow.svg" alt="System Architecture" width="100%">
</a>


## 

## Desktop Installation

### 

## Usage

Run the research assistant:

```bash
npm start
```

You'll be prompted to:

1. Enter your research query
2. Specify research breadth (recommended: 3-10, default: 4)
3. Specify research depth (recommended: 1-5, default: 2)
4. Answer follow-up questions to refine the research direction

The system will then:

1. Generate and execute search queries
2. Process and analyze search results
3. Recursively explore deeper based on findings
4. Generate a comprehensive markdown report

The final report will be saved as `output.md` in your working directory.

### Concurrency

If you have a paid version of Firecrawl or a local version, feel free to increase the `ConcurrencyLimit` in `deep-research.ts` so it runs a lot faster.

If you have a free version, you may sometime run into rate limit errors, you can reduce the limit (but it will run a lot slower).

### Custom endpoints and models

There are 2 other optional env vars that lets you tweak the endpoint (for other OpenAI compatible APIs like OpenRouter or Gemini) as well as the model string.

```bash
OPENAI_ENDPOINT="custom_endpoint"
OPENAI_MODEL="custom_model"
```

## How It Works

1. **Initial Setup**

   - Takes user query and research parameters (breadth & depth)
   - Generates follow-up questions to understand research needs better

2. **Deep Research Process**

   - Generates multiple SERP queries based on research goals
   - Processes search results to extract key learnings
   - Generates follow-up research directions

3. **Recursive Exploration**

   - If depth > 0, takes new research directions and continues exploration
   - Each iteration builds on previous learnings
   - Maintains context of research goals and findings

4. **Report Generation**
   - Compiles all findings into a comprehensive markdown report
   - Includes all sources and references
   - Organizes information in a clear, readable format

## License

MIT License - feel free to use and modify as needed.
