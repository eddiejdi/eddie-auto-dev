package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma interface que define a funcionalidade para interagir com a API do Jira.
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é uma struct que representa o Go Agent e implementa a JiraClient interface.
type GoAgentClient struct{}

func (gac GoAgentClient) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira para criar um novo issue
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// main é a função principal do programa.
func main() {
	client := GoAgentClient{}

	title := "New Feature Request"
	description := "Implement new feature in the application."

	err := client.CreateIssue(title, description)
	if err != nil {
		fmt.Println("Error creating issue:", err)
		return
	}

	fmt.Println("Issue created successfully.")
}