import { createRoot } from "react-dom/client";
import App from "./app/App.tsx";
import { setSessionAuthenticated } from "./shared/lib/apiClient";
import "./styles/index.css";

const initialDataElement = document.getElementById("initial-data");
const initialData = initialDataElement 
  ? JSON.parse(initialDataElement.textContent || "{}") 
  : { isAuthenticated: false, role: null, userName: "", currentConsultantId: null, initialPage: "login" };

// Tell the API client whether this page belongs to a signed-in user, before a
// single request can leave. On the login screen this keeps a 403
// "not_authenticated" from being mistaken for an expired session — which used
// to bounce the page back to itself every couple of seconds.
setSessionAuthenticated(Boolean(initialData.isAuthenticated));

createRoot(document.getElementById("root")!).render(<App initialData={initialData} />);
