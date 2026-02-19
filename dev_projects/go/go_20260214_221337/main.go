package main

import (
	"fmt"
	"os"
)

// JiraClient é uma interface para representar um cliente de Jira.
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgent is a struct that represents the Go Agent.
type GoAgent struct {
	JiraClient JiraClient
}

// NewGoAgent creates a new instance of GoAgent with a given JiraClient.
func NewGoAgent(jiraClient JiraClient) *GoAgent {
	return &GoAgent{jiraClient}
}

// CreateIssue is a method that creates an issue in Jira using the provided title and description.
func (g *GoAgent) CreateIssue(title string, description string) error {
	return g.JiraClient.CreateIssue(title, description)
}

// main is the entry point of the program.
func main() {
	// Example usage:
	jiraClient := NewJiraClient(&MockJiraClient{})
	goAgent := NewGoAgent(jiraClient)

	title := "New Go Agent Issue"
	description := "This is a test issue created by Go Agent."

	err := goAgent.CreateIssue(title, description)
	if err != nil {
		fmt.Println("Error creating issue:", err)
		os.Exit(1)
	}

	fmt.Println("Issue created successfully!")
}