package apidocs

import (
	"embed"
	"html/template"
	"net/http"
	"strings"
)

//go:embed assets/*
var assets embed.FS

type pageData struct {
	WSBaseURL       string
	HealthURL       string
	AsyncAPIPath    string
	PostmanPath     string
	MarkdownPath    string
	AsyncAPIPreview string
	MarkdownPreview string
}

var docsTemplate = template.Must(template.New("docs").Parse(`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QuantSync API Docs</title>
  <style>
    :root { color-scheme: light; }
    body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #f5f7fb; color: #142033; }
    main { max-width: 1100px; margin: 0 auto; padding: 32px 20px 48px; }
    h1, h2 { margin: 0 0 12px; }
    p { line-height: 1.6; }
    .hero { background: linear-gradient(135deg, #0f172a, #1e3a5f); color: #fff; padding: 28px; border-radius: 12px; }
    .hero code { background: rgba(255,255,255,0.12); padding: 2px 6px; border-radius: 6px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 20px; }
    .panel { background: #fff; border: 1px solid #d8e1ee; border-radius: 10px; padding: 18px; box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06); }
    .panel h2 { font-size: 18px; }
    .actions a { display: inline-block; margin: 8px 10px 0 0; padding: 10px 14px; border-radius: 8px; text-decoration: none; background: #0f172a; color: #fff; }
    .actions a.secondary { background: #e8eef7; color: #142033; }
    pre { overflow-x: auto; background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 10px; font-size: 13px; line-height: 1.5; }
    ul { padding-left: 18px; }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>QuantSync API Docs</h1>
      <p>REST publik sengaja minimal. Integrasi utama berjalan lewat <code>/ws</code>, dokumentasi spesifikasi tersedia di halaman ini, dan health tersedia di <code>{{.HealthURL}}</code>.</p>
      <div class="actions">
        <a href="{{.AsyncAPIPath}}">Download AsyncAPI</a>
        <a href="{{.PostmanPath}}">Download Postman Collection</a>
        <a class="secondary" href="{{.MarkdownPath}}">Open Markdown</a>
      </div>
    </section>

    <section class="grid">
      <article class="panel">
        <h2>Runtime Endpoints</h2>
        <ul>
          <li>WebSocket stream: <code>{{.WSBaseURL}}/ws?token=&lt;JWT_TOKEN&gt;</code></li>
          <li>Gateway health: <code>{{.HealthURL}}</code></li>
          <li>Docs home: <code>/api/docs</code></li>
        </ul>
      </article>
      <article class="panel">
        <h2>Tooling</h2>
        <ul>
          <li>AsyncAPI raw spec: <code>{{.AsyncAPIPath}}</code></li>
          <li>Postman collection: <code>{{.PostmanPath}}</code></li>
          <li>Markdown reference: <code>{{.MarkdownPath}}</code></li>
        </ul>
      </article>
    </section>

    <section class="grid">
      <article class="panel">
        <h2>AsyncAPI Preview</h2>
        <pre>{{.AsyncAPIPreview}}</pre>
      </article>
      <article class="panel">
        <h2>Docs Preview</h2>
        <pre>{{.MarkdownPreview}}</pre>
      </article>
    </section>
  </main>
</body>
</html>`))

func Register(mux *http.ServeMux) {
	mux.HandleFunc("/api/docs", serveDocsHome)
	mux.HandleFunc("/api/docs/", serveDocsAsset)
}

func serveDocsHome(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/api/docs" {
		http.NotFound(w, r)
		return
	}

	host := r.Host
	if host == "" {
		host = "localhost"
	}

	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}

	asyncAPI, _ := assets.ReadFile("assets/asyncapi.yaml")
	markdown, _ := assets.ReadFile("assets/API_DOCS.md")

	data := pageData{
		WSBaseURL:       "ws://" + host,
		HealthURL:       scheme + "://" + host + "/health",
		AsyncAPIPath:    "/api/docs/asyncapi.yaml",
		PostmanPath:     "/api/docs/postman.json",
		MarkdownPath:    "/api/docs/markdown",
		AsyncAPIPreview: string(asyncAPI),
		MarkdownPreview: string(markdown),
	}

	if r.TLS != nil {
		data.WSBaseURL = "wss://" + host
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_ = docsTemplate.Execute(w, data)
}

func serveDocsAsset(w http.ResponseWriter, r *http.Request) {
	switch strings.TrimPrefix(r.URL.Path, "/api/docs/") {
	case "asyncapi.yaml":
		serveEmbeddedFile(w, "assets/asyncapi.yaml", "application/yaml; charset=utf-8")
	case "postman.json":
		serveEmbeddedFile(w, "assets/postman_collection.json", "application/json; charset=utf-8")
	case "markdown":
		serveEmbeddedFile(w, "assets/API_DOCS.md", "text/markdown; charset=utf-8")
	default:
		http.NotFound(w, r)
	}
}

func serveEmbeddedFile(w http.ResponseWriter, name, contentType string) {
	body, err := assets.ReadFile(name)
	if err != nil {
		http.Error(w, "documentation asset not found", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", contentType)
	_, _ = w.Write(body)
}
