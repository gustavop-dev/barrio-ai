// «Conversación en el post» of a published piece (INT-04): each comment by thread, what the team did with it
// (answered, reacted, asked Gustavo, nothing) and the team's replies as LinkedIn shows them. Read only.
import { Link } from 'react-router-dom';
import type { PieceComment, PieceComments } from '../../api/types';
import { Badge, Section } from '../../components/ui';
import { timeAgo } from '../../lib/format';
import { COMMENT_STATUS_TONE, commentsSummary, pendingReplyLabel } from './piece';

function CommentBlock({ comment, now, answer = false }: { comment: PieceComment; now: number; answer?: boolean }) {
  const name = comment.own ? 'Tú' : comment.author.name || 'Alguien';
  const contactId = comment.own ? null : comment.author.contact_id;
  const pending = pendingReplyLabel(comment);
  return (
    <div className={answer ? 'pz-comment pz-comment-answer' : 'pz-comment'} data-testid={`comentario-${comment.id}`}>
      <div className="pz-comment-head">
        <div className="pz-comment-who">
          {contactId ? <Link to={`/personas/${contactId}`}>{name}</Link> : <span>{name}</span>}
          {comment.author.headline && !comment.own ? <p className="t-detalle text-suave">{comment.author.headline}</p> : null}
        </div>
        <Badge tone={COMMENT_STATUS_TONE[comment.status] ?? 'muted'}>{comment.status_label}</Badge>
      </div>
      <p>{comment.text}</p>
      {comment.at ? <p className="t-detalle text-suave">{timeAgo(comment.at, now)}</p> : null}
      {pending && comment.reply?.text ? (
        <div className="pz-comment-answer">
          <p className="section-label">{pending}</p>
          <p>{comment.reply.text}</p>
        </div>
      ) : pending ? (
        <p className="t-detalle text-suave">{pending}</p>
      ) : null}
    </div>
  );
}

export function PostComments({ comments, now }: { comments: PieceComments | null | undefined; now: number }) {
  if (!comments) return null;
  return (
    <Section label="Conversación en el post" id="conversacion" intro="El equipo responde solo a quien comenta, con el contexto del post y del perfil.">
      <p className="t-detalle text-suave">
        {commentsSummary(comments)}
        {comments.read_at ? ` · leído ${timeAgo(comments.read_at, now)}` : ''}
      </p>
      {comments.threads.map((thread) => (
        <div className="card compact pz-thread" key={thread.id}>
          <CommentBlock comment={thread.comment} now={now} />
          {thread.answers.map((answer) => (
            <CommentBlock key={answer.id} comment={answer} now={now} answer />
          ))}
        </div>
      ))}
    </Section>
  );
}
