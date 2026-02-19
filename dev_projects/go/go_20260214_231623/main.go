package main

import (
	"fmt"
	"log"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(issue *Issue) error
}

// Issue representa um problema ou tarefa no Jira
type Issue struct {
	Title    string `json:"title"`
	Description string `json:"description"`
	Status   string `json:"status"`
}

func main() {
	// Criando uma instância de JiraClient simulada
	jira := &MockJiraClient{}

	// Criando um novo issue
	newIssue := Issue{
		Title:    "Teste Go Agent",
		Description: "Integração com Jira",
		Status:   "Open",
	}

	// Criando uma nova tarefa no Jira
	err := jira.CreateIssue(&newIssue)
	if err != nil {
		log.Fatalf("Erro ao criar issue: %v", err)
	}

	fmt.Println("Issue criado com sucesso!")
}