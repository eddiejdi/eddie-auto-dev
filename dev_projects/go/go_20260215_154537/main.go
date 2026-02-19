package main

import (
	"fmt"
	"log"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(issue *Issue) error
	UpdateIssue(issue *Issue) error
}

// Issue representa um issue no Jira
type Issue struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Body  string `json:"body"`
}

func main() {
	// Simulação de uma conexão com o Jira API
	jiraClient := &MockJiraClient{}

	// Criando um novo issue
	newIssue := Issue{
		ID:    "12345",
		Title: "Teste do Go Agent com Jira",
		Body:  "Este é um teste para integrar o Go Agent com o Jira.",
	}

	// Criando e atualizando o issue no Jira
	err := jiraClient.CreateIssue(&newIssue)
	if err != nil {
		log.Fatalf("Erro ao criar issue: %v", err)
	}

	fmt.Println("Issue criado com sucesso!")

	err = jiraClient.UpdateIssue(&newIssue)
	if err != nil {
		log.Fatalf("Erro ao atualizar issue: %v", err)
	}

	fmt.Println("Issue atualizado com sucesso!")
}