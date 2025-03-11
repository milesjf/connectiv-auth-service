import React, { useState, useEffect, createContext, useContext } from "react";
import { CognitoUserPool, CognitoUser, AuthenticationDetails } from "amazon-cognito-identity-js";
import "./index.css";

// Instead, read the config inside a hook or component.
const getConfig = () => window.appConfig || {};

// Create a custom hook to retrieve config if needed
const useConfig = () => {
  const [config, setConfig] = useState(getConfig());

  useEffect(() => {
    // In case window.appConfig is set after component mounts
    setConfig(getConfig());
  }, []);

  return config;
};

// ------------------
// Auth Context Setup
// ------------------
const AuthContext = createContext();

const AuthProvider = ({ children }) => {
  const config = useConfig();
  // Always call hooks first
  const [loggedInUser, setLoggedInUser] = useState(null);

  // Create userPool if config is available; otherwise null.
  const userPool =
    config.REACT_APP_COGNITO_USER_POOL_ID && config.REACT_APP_COGNITO_USER_POOL_CLIENT_ID
      ? new CognitoUserPool({
          UserPoolId: config.REACT_APP_COGNITO_USER_POOL_ID,
          ClientId: config.REACT_APP_COGNITO_USER_POOL_CLIENT_ID,
        })
      : null;

  useEffect(() => {
    if (userPool) {
      const currentUser = userPool.getCurrentUser();
      if (currentUser) {
        currentUser.getSession((err, session) => {
          if (!err && session && session.isValid()) {
            console.log("✅ User is logged in:", currentUser);
            setLoggedInUser(currentUser);
          }
        });
      }
    }
  }, [userPool]);

  // Render a loading state in the returned JSX if config is missing
  return (!config.REACT_APP_COGNITO_USER_POOL_ID || !config.REACT_APP_COGNITO_USER_POOL_CLIENT_ID) ? (
    <div>Loading configuration...</div>
  ) : (
    <AuthContext.Provider value={{ loggedInUser, setLoggedInUser, userPool }}>
      {children}
    </AuthContext.Provider>
  );
};

const useAuth = () => useContext(AuthContext);

// ------------------
// Reusable Components
// ------------------
const ErrorMessage = ({ message }) => {
  if (!message) return null;
  return <p className="error-message" role="alert">{message}</p>;
};

const UserGreeting = () => {
  const { loggedInUser } = useAuth();
  return loggedInUser ? loggedInUser.getUsername().toUpperCase() : "";
};

// ------------------
// Login Form
// ------------------
const LoginForm = ({
  onSignIn,
  errorMessage,
  username,
  setUsername,
  password,
  setPassword,
  isFading,
}) => (
  <div className="card">
    <h1 className="card-title">Sign In</h1>
    <form onSubmit={onSignIn}>
      <div className="form-group">
        <label htmlFor="username" className="input-label">Username</label>
        <input
          id="username"
          className="input-field"
          type="text"
          placeholder="Enter Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
      </div>
      <div className="form-group">
        <label htmlFor="password" className="input-label">Password</label>
        <input
          id="password"
          className="input-field"
          type="password"
          placeholder="Enter Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>
      <button type="submit" className="btn btn-primary" disabled={isFading}>
        Sign In
      </button>
    </form>
    <ErrorMessage message={errorMessage} />
  </div>
);

// ------------------
// New Password Form
// ------------------
const NewPasswordForm = ({
  onNewPasswordSubmit,
  newPassword,
  setNewPassword,
  errorMessage,
  isFading,
}) => (
  <div className="card">
    <h1 className="card-title">Set New Password</h1>
    <form onSubmit={onNewPasswordSubmit}>
      <div className="form-group">
        <label htmlFor="newPassword" className="input-label">New Password</label>
        <input
          id="newPassword"
          className="input-field"
          type="password"
          placeholder="Enter New Password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
        />
      </div>
      <button type="submit" className="btn btn-primary" disabled={isFading}>
        Update Password
      </button>
    </form>
    <ErrorMessage message={errorMessage} />
  </div>
);

// ------------------
// Authenticated Content
// ------------------
const AuthenticatedContent = ({
  selectedYear,
  setSelectedYear,
  callApi,
  clearApiResponse,
  signOut,
  apiResponse,
  showResponse,
}) => (
  <div className="card">
    <h1 className="card-title">Welcome, <UserGreeting /></h1>
    <div className="form-group row">
      <label htmlFor="yearSelect" className="input-label">Select Year</label>
      <select
        id="yearSelect"
        className="input-field select-field"
        value={selectedYear}
        onChange={(e) => setSelectedYear(e.target.value)}
      >
        {Array.from({ length: 2025 - 2012 + 1 }, (_, i) => {
          const year = 2012 + i;
          return (
            <option key={year} value={year}>
              {year}
            </option>
          );
        })}
      </select>
    </div>
    <div className="btn-group">
      <button onClick={callApi} className="btn btn-primary">Fetch Missing Night Lights Data</button>
      <button onClick={clearApiResponse} className="btn btn-secondary">Clear</button>
      <button onClick={signOut} className="btn btn-secondary">Sign Out</button>
    </div>

    {showResponse && (
      <div className="api-response-wrapper">
        <div className="api-response-header">
          <span>API Response</span>
          <button onClick={clearApiResponse} className="btn btn-close">✖</button>
        </div>
        <div className="api-response-container">
          <pre className="api-response">{apiResponse}</pre>
        </div>
      </div>
    )}
  </div>
);

// ------------------
// Main App
// ------------------
function App() {
  const config = useConfig();
  const API_URL = config.REACT_APP_API_GATEWAY_URL || "";
  const { loggedInUser, setLoggedInUser, userPool } = useAuth();

  // Always call state hooks unconditionally at the top.
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isNewPasswordRequired, setIsNewPasswordRequired] = useState(false);
  const [cognitoUser, setCognitoUser] = useState(null);
  const [apiResponse, setApiResponse] = useState("");
  const [isFading, setIsFading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [showResponse, setShowResponse] = useState(false);
  const [selectedYear, setSelectedYear] = useState("2020");

  // If config isn’t loaded yet, show a loading message.
  if (!config.REACT_APP_API_GATEWAY_URL) {
    return <div>Loading configuration...</div>;
  }

  // Handles user sign in
  const signIn = (e) => {
    e.preventDefault();
    setErrorMessage("");

    if (!username || !password) {
      setErrorMessage("Please enter both username and password.");
      return;
    }

    setIsFading(true);
    // Use userPool from Auth context
    const user = new CognitoUser({ Username: username, Pool: userPool });
    const authDetails = new AuthenticationDetails({ Username: username, Password: password });

    user.authenticateUser(authDetails, {
      onSuccess: (session) => {
        console.log("✅ User signed in successfully:", session);
        setTimeout(() => {
          setLoggedInUser(user);
          setIsFading(false);
        }, 500);
      },
      onFailure: (err) => {
        console.error("❌ Login failed:", err);
        setErrorMessage("Login failed. Please check your credentials and try again.");
        setIsFading(false);
      },
      newPasswordRequired: (userAttributes, requiredAttributes) => {
        if (userAttributes.email_verified) {
          delete userAttributes.email_verified;
        }
        console.log("⚠️ New password required.");
        setIsNewPasswordRequired(true);
        setCognitoUser(user);
        setIsFading(false);
      },
    });
  };

  // Handles the new password challenge
  const handleNewPasswordSubmit = (e) => {
    e.preventDefault();
    setErrorMessage("");
    if (!newPassword) {
      setErrorMessage("Please enter a new password.");
      return;
    }
    if (!cognitoUser) {
      setErrorMessage("Unexpected error: Cognito user is not set.");
      return;
    }

  cognitoUser.completeNewPasswordChallenge(newPassword, {}, {
    onSuccess: (session) => {
      console.log("✅ Password updated and user signed in:", session);
      setLoggedInUser(cognitoUser);
      setIsNewPasswordRequired(false);
      setNewPassword("");
    },
    onFailure: (err) => {
      console.error("❌ Failed to set new password:", err);
      setErrorMessage("Failed to update password. Please try again.");
    },
  });
  };

  // Signs out the current user
  const signOut = () => {
    if (loggedInUser) {
      setIsFading(true);
      setTimeout(() => {
        loggedInUser.signOut();
        setLoggedInUser(null);
        setIsFading(false);
        setApiResponse("");
        setShowResponse(false);
      }, 500);
    }
  };

  // Calls the API ensuring that a valid session exists
  const callApi = () => {
    if (!loggedInUser) {
      setErrorMessage("You must be logged in to call the API!");
      return;
    }

    loggedInUser.getSession((err, session) => {
      if (err || !session) {
        console.error("❌ Error getting session:", err);
        setErrorMessage("Session error. Please log in again.");
        return;
      }

      if (!session.isValid()) {
        setErrorMessage("Session expired. Please log in again.");
        return;
      }

      setShowResponse(true);
      // Append a timestamp to prevent caching
      const url = `${API_URL}/hello?year_to_process=${selectedYear}&timestamp=${Date.now()}`;
      fetch(url, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${session.getIdToken().getJwtToken()}`,
        },
        cache: "no-store",
      })
        .then((res) => res.json())
        .then((data) => {
          setApiResponse(JSON.stringify(data, null, 2));
        })
        .catch((error) => {
          console.error("❌ API call failed:", error);
          setApiResponse("Failed to fetch API response.");
        });
    });
  };

  const clearApiResponse = () => {
    setApiResponse("");
    setShowResponse(false);
  };

  return (
    <div className={`app-container ${isFading ? "fade-out" : "fade-in"}`}>
      <div className="logo-container">
        <img src="/leidos_logo2.png" alt="Leidos Logo" className="logo" />
      </div>
      {isNewPasswordRequired ? (
        <NewPasswordForm
          onNewPasswordSubmit={handleNewPasswordSubmit}
          newPassword={newPassword}
          setNewPassword={setNewPassword}
          errorMessage={errorMessage}
          isFading={isFading}
        />
      ) : loggedInUser ? (
        <AuthenticatedContent
          selectedYear={selectedYear}
          setSelectedYear={setSelectedYear}
          callApi={callApi}
          clearApiResponse={clearApiResponse}
          signOut={signOut}
          apiResponse={apiResponse}
          showResponse={showResponse}
        />
      ) : (
        <LoginForm
          onSignIn={signIn}
          errorMessage={errorMessage}
          username={username}
          setUsername={setUsername}
          password={password}
          setPassword={setPassword}
          isFading={isFading}
        />
      )}
    </div>
  );
}

function RootApp() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

export default RootApp;
