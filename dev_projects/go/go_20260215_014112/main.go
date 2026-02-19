package main

import (
	"fmt"
	"log"
)

// JiraClient representa a interface para interagir com a API do Jira
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgent represents the Go Agent that will interact with Jira
type GoAgent struct {
	client JiraClient
}

// NewGoAgent creates a new instance of GoAgent
func NewGoAgent(client JiraClient) *GoAgent {
	return &GoAgent{client: client}
}

// CreateIssue creates an issue in Jira
func (g *GoAgent) CreateIssue(title string, description string) error {
	fmt.Printf("Creating issue '%s' with description:\n%s\n", title, description)
	// Simulating API call to create issue in Jira
	return nil
}

// Example usage of GoAgent
func main() {
	jiraClient := NewJiraClient(&MockJiraClient{})
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.CreateIssue("New Feature Request", "Implement a new feature for the application.")
	if err != nil {
		log.Fatalf("Error creating issue: %v", err)
	}
	fmt.Println("Issue created successfully!")
}

// MockJiraClient is a mock implementation of JiraClient
type MockJiraClient struct{}

func (m *MockJiraClient) CreateIssue(title string, description string) error {
	fmt.Printf("Creating issue '%s' with description:\n%s\n", title, description)
	// Simulating API call to create issue in Jira
	return nil
}