type SearchResult = {
  url: string;
  host: string;
  title: string;
  description: string;
  score: number;
};
type SearchReply = {
  total: number;
  limit: number;
  offset: number;
  results: SearchResult[];
};
type PageProps = {
  searchParams: Promise<{ q?: string | string[]; page?: string | string[] }>;
};

async function fetchResults(query: string, page: number): Promise<SearchReply> {
  const root = process.env.SEARCH_API_URL ?? "http://127.0.0.1:8000";
  const params = new URLSearchParams({ q: query, limit: "10", offset: String((page - 1) * 10) });
  const response = await fetch(root + "/v1/search?" + params.toString(), {
    cache: "no-store",
    signal: AbortSignal.timeout(7000),
  });
  if (!response.ok) throw new Error("Search service unavailable");
  return (await response.json()) as SearchReply;
}

function pageLink(query: string, page: number): string {
  return "/?q=" + encodeURIComponent(query) + "&page=" + page;
}

export default async function Home({ searchParams }: PageProps) {
  const params = await searchParams;
  const q = typeof params.q === "string" ? params.q.trim().slice(0, 256) : "";
  const rawPage = typeof params.page === "string" ? Number(params.page) : 1;
  const page = Number.isInteger(rawPage) && rawPage > 0 && rawPage <= 100 ? rawPage : 1;
  let reply: SearchReply | null = null;
  let unavailable = false;
  if (q.length >= 2) {
    try {
      reply = await fetchResults(q, page);
    } catch {
      unavailable = true;
    }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <a href="/" className="brand" aria-label="GoreeCloud Search home">
          <span className="brandmark" aria-hidden="true">⌕</span>
          <span>GoreeCloud <b>Search</b></span>
        </a>
        <div className="headerlinks">
          <span className="status"><span className="dot" /> Independent index · Alpha</span>
          <a href="https://github.com/GoreeCloud/search" target="_blank" rel="noopener noreferrer">
            Source code
          </a>
        </div>
      </header>
      <main className={q ? "content queried" : "content"}>
        {!q && <div className="intro">
          <span className="eyebrow">PUBLIC WEB · PRIVATE BY DESIGN</span>
          <h1>Find more. <em>Keep your freedom.</em></h1>
          <p>Web results from an index you control. No commercial search-provider dependency.</p>
        </div>}
        <form className="search" method="get" role="search" action="/">
          <label htmlFor="query" className="sr-only">Search the public web</label>
          <span className="searchicon" aria-hidden="true">⌕</span>
          <input
            id="query" type="search" name="q" defaultValue={q}
            minLength={2} maxLength={256} required
            autoComplete="off" placeholder="Search the web..." autoFocus={!q}
          />
          <button type="submit">Search <span aria-hidden="true">→</span></button>
        </form>
        {!q && <div className="features">
          <span>Independent crawling</span><span>Self-hostable</span><span>Privacy-first</span>
        </div>}
        {q && q.length < 2 && <p role="status" className="message">Enter at least 2 characters.</p>}
        {unavailable && <div role="alert" className="message error">
          Search is temporarily unavailable. Confirm the local API and OpenSearch services are running.
        </div>}
        {reply && <section className="results" aria-label="Web search results">
          <div className="resultshead">
            <p role="status">{reply.total.toLocaleString("en-US")} indexed results for <strong>{q}</strong></p>
            <span>Independent index</span>
          </div>
          {reply.results.length === 0 && <div className="message">
            No matching indexed pages yet. This early engine searches only pages that have been crawled.
          </div>}
          <div className="resultlist">
            {reply.results.map((result) => <article className="result" key={result.url}>
              <div className="domain"><span aria-hidden="true" className="siteicon">◎</span>{result.host}</div>
              <h2><a href={result.url} rel="noopener noreferrer" target="_blank">{result.title}</a></h2>
              <p>{result.description}</p>
            </article>)}
          </div>
          {(page > 1 || reply.offset + reply.results.length < reply.total) && <nav className="pagination" aria-label="Result pages">
            {page > 1 && <a href={pageLink(q, page - 1)}>← Previous</a>}
            <span>Page {page}</span>
            {page < 100 && reply.offset + reply.results.length < reply.total &&
              <a href={pageLink(q, page + 1)}>Next →</a>}
          </nav>}
        </section>}
      </main>
      <footer className="footer">
        <span>GoreeCloud Search · Development preview</span>
        <span>Privacy · Open source · Self-hosted</span>
      </footer>
    </div>
  );
}
