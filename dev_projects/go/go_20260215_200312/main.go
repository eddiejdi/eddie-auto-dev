package main

import (
	"fmt"
	"log"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
	UpdateIssue(issueID int, title string, description string) error
}

// GoAgent is the Go Agent client
type GoAgent struct{}

func (g GoAgent) CreateIssue(title string, description string) error {
	// Simulate creating an issue in Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

func (g GoAgent) UpdateIssue(issueID int, title string, description string) error {
	// Simulate updating an issue in Jira
	fmt.Printf("Updating issue %d: %s - %s\n", issueID, title, description)
	return nil
}

func main() {
	jiraClient := &GoAgent{}

	err := jiraClient.CreateIssue("New Feature Request", "Implement a new feature to improve the user experience")
	if err != nil {
		log.Fatalf("Error creating issue: %v", err)
	}

	err = jiraClient.UpdateIssue(1, "Feature Request Updated", "Now the feature is fully implemented")
	if err != nil {
		log.Fatalf("Error updating issue: %v", err)
	}
}