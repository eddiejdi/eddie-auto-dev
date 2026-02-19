package main

import (
	"fmt"
	"log"
)

// JiraClient representa um cliente para interagir com a API do Jira
type JiraClient struct {
	clientID string
}

// NewJiraClient cria uma nova instância de JiraClient
func NewJiraClient(clientID string) *JiraClient {
	return &JiraClient{clientID: clientID}
}

// CreateIssue cria um novo issue no Jira
func (jc *JiraClient) CreateIssue(summary, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue with summary: %s and description: %s\n", summary, description)
	return nil
}

// UpdateIssue atualiza um existing issue no Jira
func (jc *JiraClient) UpdateIssue(issueID string, summary, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Updating issue with ID %s, summary: %s and description: %s\n", issueID, summary, description)
	return nil
}

// DeleteIssue deleta um existing issue no Jira
func (jc *JiraClient) DeleteIssue(issueID string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Deleting issue with ID %s\n", issueID)
	return nil
}

// main é o ponto de entrada para a aplicação
func main() {
	jc := NewJiraClient("your-client-id")

	// Criar um novo issue
	err := jc.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		log.Fatalf("Error creating issue: %v\n", err)
	}

	// Atualizar um existing issue
	err = jc.UpdateIssue("12345", "Feature Request Updated", "Implemented the new feature")
	if err != nil {
		log.Fatalf("Error updating issue: %v\n", err)
	}

	// Deletar um existing issue
	err = jc.DeleteIssue("12345")
	if err != nil {
		log.Fatalf("Error deleting issue: %v\n", err)
	}
}