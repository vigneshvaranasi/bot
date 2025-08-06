import { Navigate } from "react-router-dom";

const ProtectedRoute = () => {
  const isAuthenticated = false;

  return isAuthenticated ? (
    <div>ProtectedRoute</div>
  ) : (
    <Navigate to="/" />
  );
};

export default ProtectedRoute