package main

import (
	"fmt"
	"log"
)

// JiraClient representa uma interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(summary string, description string) error
}

// GoAgent integrador com o Jira
type GoAgent struct {
	client JiraClient
}

// NewGoAgent cria um novo GoAgent com a implementação do JiraClient
func NewGoAgent(client JiraClient) *GoAgent {
	return &GoAgent{client: client}
}

// CreateIssue cria uma nova issue no Jira
func (g *GoAgent) CreateIssue(summary string, description string) error {
	log.Printf("Creating issue in Jira with summary: %s and description: %s", summary, description)
	// Simulação de chamada à API do Jira
	return nil
}

// CLI integrador com o GoAgent para testes
func main() {
	jiraClient := NewGoAgent(&MockJiraClient{})
	err := jiraClient.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		log.Fatalf("Error creating issue: %v", err)
	}
	fmt.Println("Issue created successfully!")
}

// MockJiraClient é uma implementação de JiraClient para teste
type MockJiraClient struct{}

func (m *MockJiraClient) CreateIssue(summary string, description string) error {
	log.Printf("Creating mock issue in Jira with summary: %s and description: %s", summary, description)
	// Simulação de chamada à API do Jira
	return nil
}