package main

import (
	"fmt"
	"log"

	"github.com/jenkinsci/go-agent/v4"
)

// JiraClient é uma interface para a comunicação com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentJiraClient implementa a interface JiraClient usando o Jira API
type GoAgentJiraClient struct{}

func (j GoAgentJiraClient) CreateIssue(title string, description string) error {
	// Simulação da criação de um issue no Jira
	fmt.Printf("Creating issue: %s\n", title)
	return nil
}

// Main é a função principal do programa
func main() {
	// Cria uma instância do GoAgentJiraClient
	jira := GoAgentJiraClient{}

	// Simulação da criação de um issue no Jira
	err := jira.CreateIssue("Teste de Issue", "Descrição do teste")
	if err != nil {
		log.Fatalf("Failed to create issue: %v\n", err)
	}

	fmt.Println("Issue created successfully!")
}