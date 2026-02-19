package main

import (
	"fmt"
	"log"
)

// JiraClient é uma interface para representar um cliente de Jira.
type JiraClient interface {
	CreateIssue(title, description string) error
	UpdateIssue(issueID int, title, description string) error
}

// GoAgent is a struct that represents the Go Agent.
type GoAgent struct {
	client JiraClient
}

// NewGoAgent creates a new instance of GoAgent.
func NewGoAgent(client JiraClient) *GoAgent {
	return &GoAgent{client: client}
}

// CreateIssue creates an issue in Jira.
func (ga *GoAgent) CreateIssue(title, description string) error {
	return ga.client.CreateIssue(title, description)
}

// UpdateIssue updates an existing issue in Jira.
func (ga *GoAgent) UpdateIssue(issueID int, title, description string) error {
	return ga.client.UpdateIssue(issueID, title, description)
}

// main is the entry point of the program.
func main() {
	// Example usage
	jiraClient := NewJiraClient(&MockJiraClient{})
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.CreateIssue("New Feature", "Implement a new feature in the application.")
	if err != nil {
		log.Fatalf("Error creating issue: %v", err)
	}

	err = goAgent.UpdateIssue(123, "Feature Implemented", "The new feature is now live.")
	if err != nil {
		log.Fatalf("Error updating issue: %v", err)
	}
}