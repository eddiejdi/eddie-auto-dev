package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma interface que define as operações básicas para interagir com a API do Jira.
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é uma implementação da interface JiraClient usando o Go Agent SDK.
type GoAgentClient struct{}

func (gac GoAgentClient) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Go Agent para criar um issue no Jira.
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// JiraAPI é uma struct que representa a API do Jira.
type JiraAPI struct{}

func (ja JiraAPI) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira para criar um issue no Jira.
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// main é a função principal que executa o programa.
func main() {
	jac := GoAgentClient{}
	ja.CreateIssue("Test Issue", "This is a test issue created by Go Agent.")

	ja2 := JiraAPI{}
	err := ja2.CreateIssue("Another Test Issue", "This is another test issue created by Jira API.")
	if err != nil {
		fmt.Println(err)
	}
}