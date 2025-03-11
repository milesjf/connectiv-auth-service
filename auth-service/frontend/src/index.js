// index.js
import React from "react";
import ReactDOM from "react-dom";
import RootApp from "./App";

fetch("/config.json")
  .then((response) => {
    if (!response.ok) {
      throw new Error("Failed to load config.json");
    }
    return response.json();
  })
  .then((config) => {
    window.appConfig = config;
    ReactDOM.render(<RootApp />, document.getElementById("root"));
  })
  .catch((error) => {
    console.error("Failed to load configuration:", error);
    // Optionally render an error state
  });
