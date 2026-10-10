import { createRoot } from "react-dom/client";
import App from "./app/App.tsx";
import { setSessionAuthenticated } from "./shared/lib/apiClient";
import "./styles/index.css";

const initialDataElement = document.getElementById("initial-data");
const initialData = initialDataElement 
  ? JSON.parse(initialDataElement.textContent || "{}") 
  : { isAuthenticated: false, role: null, userName: "", currentConsultantId: null, initialPage: "login" };

setSessionAuthenticated(Boolean(initialData.isAuthenticated));

createRoot(document.getElementById("root")!).render(<App initialData={initialData} />);
