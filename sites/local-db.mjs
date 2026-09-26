import {DatabaseSync} from 'node:sqlite';
import {readFileSync,readdirSync} from 'node:fs';
export function localDB(filename=':memory:'){
  const db=new DatabaseSync(filename);
  db.exec('CREATE TABLE IF NOT EXISTS local_migrations(name TEXT PRIMARY KEY)');
  for(const name of readdirSync('drizzle').filter(n=>n.endsWith('.sql')).sort()){
    if(!db.prepare('SELECT 1 FROM local_migrations WHERE name=?').get(name)){
      db.exec(readFileSync('drizzle/'+name,'utf8'));db.prepare('INSERT INTO local_migrations VALUES(?)').run(name);
    }
  }
  return {prepare(sql){const stmt=db.prepare(sql);let args=[];const wrapper={bind(...values){args=values;return wrapper;},async first(){return stmt.get(...args)||null;},async run(){const result=stmt.run(...args);return {meta:{changes:Number(result.changes)}};}};return wrapper;},close(){db.close();}};
}
