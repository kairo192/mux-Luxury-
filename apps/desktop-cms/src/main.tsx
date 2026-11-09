import React, { Component, ErrorInfo, ReactNode } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { I18nProvider } from "./i18n";
import "./index.css";

// Native Desktop Software Behavior: disable web right-click menu (Inspect Element) & browser dev shortcuts
if (typeof window !== "undefined") {
  window.addEventListener("contextmenu", (e) => e.preventDefault());
  window.addEventListener("keydown", (e) => {
    if (
      e.key === "F12" ||
      e.key === "F5" ||
      (e.ctrlKey && e.shiftKey && ["I", "i", "C", "c", "J", "j"].includes(e.key)) ||
      (e.ctrlKey && ["r", "R", "u", "U", "p", "P"].includes(e.key))
    ) {
      e.preventDefault();
    }
  });
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class RootErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("RootErrorBoundary caught:", error, errorInfo);
    this.setState({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 32, fontFamily: "system-ui, sans-serif", background: "#FFF5F5", minHeight: "100vh", color: "#9B1C1C" }}>
          <h1 style={{ fontSize: 24, fontWeight: "bold", marginBottom: 16 }}>Une erreur d'affichage est survenue</h1>
          <p style={{ fontWeight: 600, fontSize: 16 }}>{this.state.error?.toString()}</p>
          <pre style={{ background: "#202923", color: "#F8F6F0", padding: 16, borderRadius: 8, overflowX: "auto", fontSize: 12, marginTop: 16 }}>
            {this.state.error?.stack}
          </pre>
          <button
            onClick={() => {
              localStorage.clear();
              window.location.reload();
            }}
            style={{ marginTop: 24, padding: "10px 20px", background: "#063D2E", color: "#D4AF62", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: "bold" }}
          >
            Réinitialiser le cache et Recharger
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <RootErrorBoundary>
    <I18nProvider>
      <App />
    </I18nProvider>
  </RootErrorBoundary>
);
