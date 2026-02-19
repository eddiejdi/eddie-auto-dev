package main

import (
	"fmt"
	"log"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient struct {
	token string
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(token string) *JiraClient {
	return &JiraClient{token: token}
}

// CreateIssue cria um novo issue no Jira
func (jc *JiraClient) CreateIssue(issueTitle, issueDescription string) error {
	// Simulação da chamada à API do Jira
	fmt.Printf("Creating issue '%s' with description '%s'\n", issueTitle, issueDescription)
	return nil
}

// UpdateIssue atualiza um existing issue no Jira
func (jc *JiraClient) UpdateIssue(issueKey string, newTitle, newDescription string) error {
	// Simulação da chamada à API do Jira
	fmt.Printf("Updating issue '%s' with new title '%s' and description '%s'\n", issueKey, newTitle, newDescription)
	return nil
}

func main() {
	token := "your-jira-token"
	jiraClient := NewJiraClient(token)

	// Criando um novo issue
	err := jiraClient.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		log.Fatalf("Error creating issue: %v", err)
	}

	// Atualizando um existing issue
	err = jiraClient.UpdateIssue("JIRA-123", "Feature Implemented", "The new feature has been successfully implemented.")
	if err != nil {
		log.Fatalf("Error updating issue: %v", err)
	}
}