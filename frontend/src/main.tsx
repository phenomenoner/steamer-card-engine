import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

class RootErrorBoundary extends React.Component<React.PropsWithChildren, { error: string | null }> {
  constructor(props: React.PropsWithChildren) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: unknown) {
    return { error: error instanceof Error ? error.message : String(error) };
  }

  override componentDidCatch(error: unknown) {
    console.error("steamer-dashboard root crash", error);
  }

  override render() {
    if (this.state.error) {
      return <div className="state-block text-alert">ROOT UI ERROR: {this.state.error}</div>;
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  </React.StrictMode>,
);
