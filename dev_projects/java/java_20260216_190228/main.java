import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.security.JiraAuthenticationContext;
import com.atlassian.jira.service.ServiceContextFactory;

public class JavaAgent {

    public static void main(String[] args) {
        // Cria um contexto de serviço para JIRA
        JiraServiceContext serviceContext = ServiceContextFactory.getJiraServiceContext();

        // Cria uma autenticação para JIRA
        JiraAuthenticationContext authenticationContext = new JiraAuthenticationContext(serviceContext);

        // Cria uma instância do Jira
        Jira jira = new Jira(authenticationContext);

        // Exemplo de uso: Adicionar uma tarefa em JIRA
        String issueKey = "TEST-1";
        String summary = "Teste da Tarefa";

        try {
            jira.createIssue(issueKey, summary);
            System.out.println("Tarefa adicionada com sucesso!");
        } catch (Exception e) {
            System.err.println("Erro ao adicionar tarefa: " + e.getMessage());
        }
    }
}