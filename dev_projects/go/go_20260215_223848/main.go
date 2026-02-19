package main

import (
	"fmt"
	"log"
)

// JiraClient é uma interface para interagir com a API do Jira
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é uma interface para interagir com o Go Agent
type GoAgentClient interface {
	SendStatus(status string) error
}

// JiraService implementa a interface JiraClient
type JiraService struct{}

func (js *JiraService) CreateIssue(title string, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue in Jira: %s\n", title)
	return nil
}

// GoAgentService implementa a interface GoAgentClient
type GoAgentService struct{}

func (gas *GoAgentService) SendStatus(status string) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Sending status to Go Agent: %s\n", status)
	return nil
}

// Main é a função principal que implementa o fluxo da integração
func main() {
	jiraClient := &JiraService{}
	goAgentClient := &GoAgentService{}

	// Simulação de criação de issue no Jira
	err := jiraClient.CreateIssue("Bug in Go Agent", "The Go Agent is not working as expected.")
	if err != nil {
		log.Fatalf("Failed to create issue in Jira: %v\n", err)
	}

	// Simulação de envio de status para o Go Agent
	err = goAgentClient.SendStatus("Running")
	if err != nil {
		log.Fatalf("Failed to send status to Go Agent: %v\n", err)
	}
}