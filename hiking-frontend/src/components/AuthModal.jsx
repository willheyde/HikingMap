import { useState } from "react";
// 1. IMPORT NAVIGATE
import { useNavigate } from "react-router-dom"; 
import { useUser } from "../context/UserContext";

const AuthModal = () => {
  // Added setAuthModalOpen (assuming you have a way to close it in context) to clean up UI
  const { authModalOpen, setAuthModalOpen, login, createUser, loading, error } = useUser();
  const [isLoginView, setIsLoginView] = useState(true);
  
  // 2. INITIALIZE HOOK
  const navigate = useNavigate(); 

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  if (!authModalOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (isLoginView) {
        await login(email, password);
        // 3a. LOGIN REDIRECT: Send returning users to their profile
        navigate("/profile");
      } else {
        await createUser({
            email,
            password, 
            name,
            avatar_url: null, 
            home_location: null, 
            timezone: "UTC"
        });
        // 3b. SIGNUP REDIRECT: Send NEW users to your gamified setup
        navigate("/onboarding"); 
      }
      
      // Close the modal upon success (if your context supports this)
      if (setAuthModalOpen) setAuthModalOpen(false);

      // Clear form
      setEmail("");
      setPassword("");
      setName("");
    } catch (err) {
      console.error("Auth error:", err);
    }
  };

  const handleToggleView = () => {
    setIsLoginView(!isLoginView);
    setEmail("");
    setPassword("");
    setName("");
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-8 max-w-sm w-full shadow-2xl">
        
        <h2 className="text-2xl font-bold mb-6 text-center text-gray-800">
          {isLoginView ? "Welcome Back" : "Create Account"}
        </h2>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded mb-4 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLoginView && (
            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input 
                type="text" 
                required 
                className="mt-1 block w-full border border-gray-300 rounded-md p-2 focus:ring-2 focus:ring-green-500 focus:border-transparent"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="John Doe"
              />
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium text-gray-700">Email</label>
            <input 
              type="email" 
              required 
              className="mt-1 block w-full border border-gray-300 rounded-md p-2 focus:ring-2 focus:ring-green-500 focus:border-transparent"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Password</label>
            <input 
              type="password" 
              required 
              minLength={6}
              className="mt-1 block w-full border border-gray-300 rounded-md p-2 focus:ring-2 focus:ring-green-500 focus:border-transparent"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
            {!isLoginView && (
              <p className="mt-1 text-xs text-gray-500">Minimum 6 characters</p>
            )}
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 transition disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {loading ? "Please wait..." : (isLoginView ? "Log In" : "Sign Up")}
          </button>
        </form>

        <div className="mt-4 text-center text-sm">
          <span className="text-gray-600">
            {isLoginView ? "New here? " : "Already have an account? "}
          </span>
          <button 
            onClick={handleToggleView}
            type="button"
            className="text-green-600 font-semibold hover:underline"
            disabled={loading}
          >
            {isLoginView ? "Create an account" : "Log In"}
          </button>
        </div>

      </div>
    </div>
  );
};

export default AuthModal;