package main_test

import (
	"testing"
)

// TestConfigValid checks if the Config struct is valid with provided values.
func TestConfigValid(t *testing.T) {
	config := agent.DefaultConfig()
	config.JiraServerURL = "https://your-jira-server.com"
	config.JiraUsername = "your-username"
	config.JiraPassword = "your-password"

	if err := config.Validate(); err != nil {
		t.Errorf("Invalid configuration: %v", err)
	}
}

// TestStartValid checks if the Start method returns an error with provided values.
func TestStartValid(t *testing.T) {
	config := agent.DefaultConfig()
	config.JiraServerURL = "https://your-jira-server.com"
	config.JiraUsername = "your-username"
	config.JiraPassword = "your-password"

	goAgent, err := agent.New(config)
	if err != nil {
		t.Errorf("Failed to create Go Agent: %v", err)
	}

	err = goAgent.Start()
	if err == nil {
		t.Errorf("Start method should return an error")
	}
}

// TestStartValid checks if the Start method returns an error with provided values.
func TestStartValid(t *testing.T) {
	config := agent.DefaultConfig()
	config.JiraServerURL = "https://your-jira-server.com"
	config.JiraUsername = "your-username"
	config.JiraPassword = "your-password"

	goAgent, err := agent.New(config)
	if err != nil {
		t.Errorf("Failed to create Go Agent: %v", err)
	}

	err = goAgent.Start()
	if err == nil {
		t.Errorf("Start method should return an error")
	}
}