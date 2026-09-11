import { createContext, useContext, useState, useEffect } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem("konnect_user");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    try {
      if (user) {
        localStorage.setItem("konnect_user", JSON.stringify(user));
      } else {
        localStorage.removeItem("konnect_user");
      }
    } catch {
      // ignore storage errors
    }
  }, [user]);

  const login = (email, _password) => {
    // Dummy login validation
    const dummyUser = {
      name: email.split("@")[0].replace(".", " ").replace(/\b\w/g, (c) => c.toUpperCase()) || "Demo User",
      email: email || "researcher@konnect.ai",
      role: "Verified Researcher",
      joined: new Date().toLocaleDateString(),
    };
    setUser(dummyUser);
    return true;
  };

  const signup = (name, email, _password) => {
    // Dummy signup
    const newUser = {
      name: name || "New User",
      email: email || "user@konnect.ai",
      role: "Workspace Member",
      joined: new Date().toLocaleDateString(),
    };
    setUser(newUser);
    return true;
  };

  const loginAsDemo = () => {
    const demoUser = {
      name: "Demo Researcher",
      email: "demo@konnect.ai",
      role: "Full Access Demo",
      avatar: "DR",
      joined: "Today",
    };
    setUser(demoUser);
    return demoUser;
  };

  const logout = () => {
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        login,
        signup,
        loginAsDemo,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
