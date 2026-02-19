package main

import (
	"fmt"
	"log"
)

// JiraClient é uma interface para a comunicação com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
	UpdateIssue(issueID int, title string, description string) error
}

// GoAgent is the Go Agent component that integrates with Jira
type GoAgent struct {
	client JiraClient
}

// NewGoAgent creates a new instance of GoAgent
func NewGoAgent(client JiraClient) *GoAgent {
	return &GoAgent{client: client}
}

// CreateIssue creates a new issue in Jira
func (ga *GoAgent) CreateIssue(title string, description string) error {
	_, err := ga.client.CreateIssue(title, description)
	if err != nil {
		log.Fatalf("Failed to create issue: %v", err)
	}
	return nil
}

// UpdateIssue updates an existing issue in Jira
func (ga *GoAgent) UpdateIssue(issueID int, title string, description string) error {
	_, err := ga.client.UpdateIssue(issueID, title, description)
	if err != nil {
		log.Fatalf("Failed to update issue: %v", err)
	}
	return nil
}

// Example usage of GoAgent
func main() {
	client := NewJiraClient(&MockJiraClient{})
	ga := NewGoAgent(client)

	err := ga.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		fmt.Println(err)
	} else {
		fmt.Println("Issue created successfully.")
	}

	err = ga.UpdateIssue(1, "Updated Test Issue", "This is an updated test issue.")
	if err != nil {
		fmt.Println(err)
	} else {
		fmt.Println("Issue updated successfully.")
	}
}