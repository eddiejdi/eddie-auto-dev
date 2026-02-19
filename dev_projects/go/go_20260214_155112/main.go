package main

import (
	"fmt"
	"log"
)

// JiraClient é a interface para interagir com o sistema Jira
type JiraClient interface {
	CreateIssue(title string, description string) error
	UpdateIssue(issueID int, title string, description string) error
}

// GoAgent is the Go Agent client for interacting with Jira
type GoAgent struct{}

func (g GoAgent) CreateIssue(title string, description string) error {
	// Simulação da criação de um issue em Jira
	fmt.Printf("Creating issue '%s': %s\n", title, description)
	return nil
}

func (g GoAgent) UpdateIssue(issueID int, title string, description string) error {
	// Simulação da atualização de um issue em Jira
	fmt.Printf("Updating issue %d: %s\n", issueID, description)
	return nil
}

// main is the entry point of the application
func main() {
	client := GoAgent{}

	// Create an issue
	err := client.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		log.Fatalf("Error creating issue: %s\n", err)
	}

	// Update an issue
	err = client.UpdateIssue(123, "Feature Request Updated", "Implement a new feature in the application")
	if err != nil {
		log.Fatalf("Error updating issue: %s\n", err)
	}
}