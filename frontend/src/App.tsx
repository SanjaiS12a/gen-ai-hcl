import { createContext, useContext, useState } from "react";
import { NavLink, Route, Routes, Link } from "react-router-dom";
import { ShieldCheck, ListFilter, History, Settings } from "lucide-react";
import Queue from "./pages/Queue";
import Detail from "./pages/Detail";
import HistoryPage from "./pages/History";
import SettingsPage from "./pages/Settings";
import { SystemStatus } from "./components/Common";

const Preferences = createContext({
  rulesOnly: false,
  setRulesOnly: (_value: boolean) => {},
});
export const usePreferences = () => useContext(Preferences);

export default function App() {
  const [rulesOnly, setValue] = useState(
    localStorage.getItem("soc-rules-only") === "true",
  );
  function setRulesOnly(value: boolean) {
    localStorage.setItem("soc-rules-only", String(value));
    setValue(value);
  }
  return (
    <Preferences.Provider value={{ rulesOnly, setRulesOnly }}>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <div className="shell">
        <aside className="sidebar">
          <Link className="brand" to="/">
            <ShieldCheck size={28} />
            <span>
              SOC / LOCAL<small>Incident-response copilot</small>
            </span>
          </Link>
          <div className="nav-label">WORKSPACE</div>
          <nav aria-label="Main navigation">
            <NavLink end to="/">
              <ListFilter size={18} /> Alert queue
            </NavLink>
            <NavLink to="/history">
              <History size={18} /> History & audit
            </NavLink>
            <NavLink to="/settings">
              <Settings size={18} /> Settings
            </NavLink>
          </nav>
          <div className="sidebar-foot">
            <span className="local-dot" /> Local processing
            <small>
              Recommendations only.
              <br />
              Analyst approval before action.
            </small>
          </div>
        </aside>
        <div className="workspace">
          <SystemStatus />
          <main id="main">
            <Routes>
              <Route path="/" element={<Queue />} />
              <Route path="/alerts/:id" element={<Detail />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route
                path="*"
                element={
                  <>
                    <h1>Page not found</h1>
                    <Link to="/">Return to queue</Link>
                  </>
                }
              />
            </Routes>
          </main>
        </div>
      </div>
    </Preferences.Provider>
  );
}
