import { useRoutes } from "react-router"
import routes from "./router"

function App() {
  const content = useRoutes(routes);
  return content;
}

export default App