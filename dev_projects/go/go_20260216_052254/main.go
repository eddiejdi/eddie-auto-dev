package main

import (
	"fmt"
	"log"

	"github.com/jenkinsci/go-agent/v4"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient struct{}

// CreateIssue cria um novo issue no Jira
func (j *JiraClient) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// UpdateIssue atualiza um existing issue no Jira
func (j *JiraClient) UpdateIssue(issueID int, title, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Updating issue %d: %s - %s\n", issueID, title, description)
	return nil
}

// DeleteIssue remove um existing issue no Jira
func (j *JiraClient) DeleteIssue(issueID int) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Deleting issue %d\n", issueID)
	return nil
}

// Main é a função principal que inicia o programa
func main() {
	jira := &JiraClient{}

	// Criando um novo issue
	err := jira.CreateIssue("Bug Fix", "Fixes the login page")
	if err != nil {
		log.Fatalf("Failed to create issue: %v\n", err)
	}

	// Atualizando um existing issue
	err = jira.UpdateIssue(1, "New Feature", "Adds a new feature to the application")
	if err != nil {
		log.Fatalf("Failed to update issue: %v\n", err)
	}

	// Removendo um existing issue
	err = jira.DeleteIssue(2)
	if err != nil {
		log.Fatalf("Failed to delete issue: %v\n", err)
	}
}