import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.util.JiraUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgent {

    @Autowired
    private JiraUtils jiraUtils;

    public void trackActivity(Issue issue, String activity) {
        try {
            // Simula a adição de atividade ao issue
            issue.addComment(activity);
            System.out.println("Atividade adicionada com sucesso: " + activity);
        } catch (Exception e) {
            System.err.println("Erro ao adicionar atividade ao issue: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgent javaAgent = new JavaAgent();
        Issue issue = jiraUtils.getIssueByKey("YOUR_ISSUE_KEY");
        if (issue != null) {
            javaAgent.trackActivity(issue, "Novo comentário adicionado pelo Java Agent");
        } else {
            System.err.println("Issue não encontrado: YOUR_ISSUE_KEY");
        }
    }
}